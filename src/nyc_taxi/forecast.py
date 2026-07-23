"""Time-aware hourly taxi-zone demand forecasting."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .events import event_features


LAGS = (1, 2, 24, 168)
ROLLING_WINDOWS = (3, 6, 24)
AIRPORT_ZONE_IDS = (132, 138)
MODEL_FEATURES = [
    "pickup_zone_id",
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_us_holiday",
    "event_code",
    "is_event_window",
    "is_event_eve",
    "is_event_overnight",
    "is_new_year_window",
    "hours_to_major_event",
    "hours_since_major_event",
    "is_airport_zone",
    "temperature_c",
    "precipitation_mm",
    "weather_missing",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    *[f"lag_{lag}" for lag in LAGS],
    *[f"rolling_mean_{window}" for window in ROLLING_WINDOWS],
]


@dataclass(frozen=True)
class TimeSplit:
    train_end: str
    validation_month: str
    test_month: str


def load_hourly(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = duckdb.connect()
    frame = connection.execute(
        f"""SELECT pickup_zone_id, pickup_hour, trip_count
        FROM read_parquet('{path.resolve().as_posix()}')
        ORDER BY pickup_hour, pickup_zone_id"""
    ).fetchdf()
    connection.close()
    frame["pickup_hour"] = pd.to_datetime(frame["pickup_hour"])
    return frame


def _us_holiday(timestamp: pd.Series) -> pd.Series:
    """Small deterministic calendar feature; observed-day policy is intentionally excluded."""
    dates = timestamp.dt.strftime("%m-%d")
    fixed = dates.isin({"01-01", "06-19", "07-04", "11-11", "12-25"})
    nth = (
        ((timestamp.dt.day - 1) // 7 + 1).astype(int).astype(str)
        + "-" + timestamp.dt.dayofweek.astype(str)
        + "-" + timestamp.dt.month.astype(str)
    )
    movable = nth.isin({"3-0-1", "3-0-2", "4-0-5", "1-0-9", "4-3-11"})
    thanksgiving = (timestamp.dt.month.eq(11) & timestamp.dt.dayofweek.eq(3)
                    & timestamp.dt.day.between(22, 28))
    return (fixed | movable | thanksgiving).astype(int)


def make_feature_table(hourly: pd.DataFrame, weather: pd.DataFrame | None = None) -> pd.DataFrame:
    """Create a complete zone-hour grid and leakage-safe historical features."""
    required = {"pickup_zone_id", "pickup_hour", "trip_count"}
    missing = required.difference(hourly.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    source = hourly.copy()
    source["pickup_hour"] = pd.to_datetime(source["pickup_hour"])
    source = source.groupby(["pickup_zone_id", "pickup_hour"], as_index=False)[
        "trip_count"
    ].sum()
    zones = np.sort(source["pickup_zone_id"].dropna().astype(int).unique())
    hours = pd.date_range(
        source["pickup_hour"].min().floor("h"),
        source["pickup_hour"].max().floor("h"),
        freq="h",
    )
    grid = pd.MultiIndex.from_product(
        [zones, hours], names=["pickup_zone_id", "pickup_hour"]
    ).to_frame(index=False)
    frame = grid.merge(source, on=["pickup_zone_id", "pickup_hour"], how="left")
    frame["trip_count"] = frame["trip_count"].fillna(0).astype(float)
    frame = frame.sort_values(["pickup_zone_id", "pickup_hour"]).reset_index(drop=True)

    timestamp = frame["pickup_hour"]
    frame["hour"] = timestamp.dt.hour
    frame["day_of_week"] = timestamp.dt.dayofweek
    frame["month"] = timestamp.dt.month
    frame["is_weekend"] = timestamp.dt.dayofweek.ge(5).astype(int)
    frame["is_us_holiday"] = _us_holiday(timestamp)
    calendar = pd.DataFrame({"pickup_hour": timestamp.drop_duplicates().sort_values()})
    calendar = pd.concat([calendar, event_features(calendar["pickup_hour"])], axis=1)
    frame = frame.merge(calendar, on="pickup_hour", how="left")
    frame["is_airport_zone"] = frame["pickup_zone_id"].isin(AIRPORT_ZONE_IDS).astype(int)
    if weather is not None:
        weather = weather.copy()
        weather["pickup_hour"] = pd.to_datetime(weather["pickup_hour"]).dt.floor("h")
        required_weather = {"pickup_hour", "temperature_c", "precipitation_mm"}
        if missing_weather := required_weather.difference(weather.columns):
            raise ValueError(f"Missing weather columns: {', '.join(sorted(missing_weather))}")
        frame = frame.merge(weather[list(required_weather)], on="pickup_hour", how="left")
    else:
        frame["temperature_c"] = np.nan
        frame["precipitation_mm"] = np.nan
    frame["weather_missing"] = frame["temperature_c"].isna().astype(int)
    frame["temperature_c"] = frame["temperature_c"].fillna(0.0)
    frame["precipitation_mm"] = frame["precipitation_mm"].fillna(0.0)
    frame["hour_sin"] = np.sin(2 * np.pi * frame["hour"] / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * frame["hour"] / 24)
    frame["dow_sin"] = np.sin(2 * np.pi * frame["day_of_week"] / 7)
    frame["dow_cos"] = np.cos(2 * np.pi * frame["day_of_week"] / 7)
    grouped = frame.groupby("pickup_zone_id", sort=False)["trip_count"]
    for lag in LAGS:
        frame[f"lag_{lag}"] = grouped.shift(lag)
    for window in ROLLING_WINDOWS:
        frame[f"rolling_mean_{window}"] = grouped.transform(
            lambda values: values.shift(1).rolling(window, min_periods=window).mean()
        )
    return frame.dropna(subset=MODEL_FEATURES).reset_index(drop=True)


def time_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, TimeSplit]:
    months = frame["pickup_hour"].dt.to_period("M")
    unique_months = sorted(months.unique())
    if len(unique_months) < 3:
        raise ValueError("At least three calendar months are required for time-aware splitting")
    validation_month, test_month = unique_months[-2:]
    train = frame.loc[months < validation_month].copy()
    validation = frame.loc[months == validation_month].copy()
    test = frame.loc[months == test_month].copy()
    split = TimeSplit(
        train_end=str(validation_month - 1),
        validation_month=str(validation_month),
        test_month=str(test_month),
    )
    return train, validation, test, split


def metrics(y_true: pd.Series, prediction: np.ndarray, high_threshold: float) -> dict[str, float]:
    prediction = np.clip(np.asarray(prediction, dtype=float), 0, None)
    truth = np.asarray(y_true, dtype=float)
    actual_high = truth >= high_threshold
    predicted_high = prediction >= high_threshold
    true_positive = int(np.logical_and(actual_high, predicted_high).sum())
    precision_denominator = int(predicted_high.sum())
    recall_denominator = int(actual_high.sum())
    return {
        "mae": float(mean_absolute_error(truth, prediction)),
        "rmse": float(mean_squared_error(truth, prediction) ** 0.5),
        "wape": float(np.abs(truth - prediction).sum() / max(truth.sum(), 1.0)),
        "high_demand_precision": true_positive / max(precision_denominator, 1),
        "high_demand_recall": true_positive / max(recall_denominator, 1),
    }


def segment_errors(test: pd.DataFrame, prediction: np.ndarray) -> dict[str, object]:
    scored = test[["pickup_zone_id", "pickup_hour", "trip_count"]].copy()
    scored["prediction"] = np.clip(prediction, 0, None)
    scored["absolute_error"] = (scored["trip_count"] - scored["prediction"]).abs()
    scored["hour"] = scored["pickup_hour"].dt.hour

    def summarize(grouped):
        output = []
        for key, group in grouped:
            output.append(
                {
                    "segment": int(key),
                    "rows": len(group),
                    "mae": float(group["absolute_error"].mean()),
                    "wape": float(
                        group["absolute_error"].sum() / max(group["trip_count"].sum(), 1.0)
                    ),
                }
            )
        return output

    by_hour = summarize(scored.groupby("hour", sort=True))
    by_zone = summarize(scored.groupby("pickup_zone_id", sort=True))
    worst_zones = sorted(by_zone, key=lambda row: row["mae"], reverse=True)[:10]
    return {"by_hour": by_hour, "worst_zones_by_mae": worst_zones}


def train_forecast(
    hourly_path: Path,
    output_dir: Path,
    *,
    max_iter: int = 120,
    weather_path: Path | None = None,
) -> dict[str, object]:
    weather = pd.read_csv(weather_path) if weather_path else None
    features = make_feature_table(load_hourly(hourly_path), weather)
    train, validation, test, split = time_split(features)
    threshold = float(train["trip_count"].quantile(0.9))

    model = HistGradientBoostingRegressor(
        loss="poisson",
        learning_rate=0.08,
        max_iter=max_iter,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=42,
    )
    model.fit(train[MODEL_FEATURES], train["trip_count"])
    validation_predictions = model.predict(validation[MODEL_FEATURES])
    linear = Ridge(alpha=10.0)
    linear.fit(train[MODEL_FEATURES], train["trip_count"])
    linear_validation_predictions = linear.predict(validation[MODEL_FEATURES])

    final_model = HistGradientBoostingRegressor(
        loss="poisson",
        learning_rate=0.08,
        max_iter=max_iter,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=42,
    )
    train_and_validation = pd.concat([train, validation], ignore_index=True)
    final_model.fit(train_and_validation[MODEL_FEATURES], train_and_validation["trip_count"])
    model_predictions = final_model.predict(test[MODEL_FEATURES])

    report = {
        "split": asdict(split),
        "rows": {
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
        },
        "high_demand_threshold": threshold,
        "validation": {
            "ridge": metrics(validation["trip_count"], linear_validation_predictions, threshold),
            "hist_gradient_boosting": metrics(
                validation["trip_count"], validation_predictions, threshold
            )
        },
        "test": {
            "previous_hour": metrics(test["trip_count"], test["lag_1"].to_numpy(), threshold),
            "previous_day": metrics(test["trip_count"], test["lag_24"].to_numpy(), threshold),
            "previous_week": metrics(test["trip_count"], test["lag_168"].to_numpy(), threshold),
            "hist_gradient_boosting": metrics(test["trip_count"], model_predictions, threshold),
        },
        "test_segments": segment_errors(test, model_predictions),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": final_model, "features": MODEL_FEATURES, "split": asdict(split)},
        output_dir / "demand_forecast.joblib",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    predictions = test[["pickup_zone_id", "pickup_hour", "trip_count"]].copy()
    predictions["prediction"] = np.clip(model_predictions, 0, None)
    connection = duckdb.connect()
    connection.register("predictions", predictions)
    connection.execute(
        f"COPY predictions TO '{(output_dir / 'test_predictions.parquet').resolve().as_posix()}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    connection.close()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train an hourly taxi demand forecast")
    parser.add_argument(
        "--input", type=Path, default=Path("data/processed/hourly_zone_demand.parquet")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("models/demand_forecast"))
    parser.add_argument("--max-iter", type=int, default=120)
    parser.add_argument("--weather", type=Path, help="optional hourly CSV with temperature_c and precipitation_mm")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = train_forecast(args.input, args.output_dir, max_iter=args.max_iter, weather_path=args.weather)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
