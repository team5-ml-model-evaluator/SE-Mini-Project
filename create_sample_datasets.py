import os
import random
import numpy as np
import pandas as pd
from pathlib import Path

DATASETS_DIR = Path("sample_datasets")
DATASETS_DIR.mkdir(exist_ok=True)

def generate_all_datasets():
    np.random.seed(42)
    random.seed(42)
    n = 100

    # 1. Customer Churn (Classification)
    age = np.random.randint(21, 68, n)
    monthly_charges = np.random.uniform(28.0, 115.0, n).round(2)
    tenure_months = np.random.randint(1, 65, n)
    z1 = -2.2 + (0.035 * age) + (0.045 * monthly_charges) - (0.055 * tenure_months) + np.random.normal(0, 0.75, n)
    churn = (1 / (1 + np.exp(-z1)) > 0.5).astype(int)
    df_churn = pd.DataFrame({
        "age": age,
        "monthly_charges": monthly_charges,
        "tenure_months": tenure_months,
        "churned": churn
    })
    df_churn.to_csv(DATASETS_DIR / "customer_churn_analysis.csv", index=False)

    # 2. Credit Risk (Classification)
    credit_score = np.random.randint(520, 820, n)
    debt_ratio = np.random.uniform(0.12, 0.65, n).round(2)
    annual_income_k = np.random.randint(28, 140, n)
    z2 = 3.5 - (0.007 * credit_score) + (3.2 * debt_ratio) - (0.02 * annual_income_k) + np.random.normal(0, 0.6, n)
    defaulted = (1 / (1 + np.exp(-z2)) > 0.45).astype(int)
    df_credit = pd.DataFrame({
        "credit_score": credit_score,
        "debt_ratio": debt_ratio,
        "annual_income_k": annual_income_k,
        "loan_default": defaulted
    })
    df_credit.to_csv(DATASETS_DIR / "credit_risk_assessment.csv", index=False)

    # 3. Patient Health Risk (Classification)
    bp = np.random.randint(105, 175, n)
    bmi = np.random.uniform(19.0, 38.0, n).round(1)
    glucose = np.random.randint(75, 190, n)
    z3 = -4.0 + (0.025 * bp) + (0.08 * bmi) + (0.015 * glucose) + np.random.normal(0, 0.7, n)
    high_risk = (1 / (1 + np.exp(-z3)) > 0.5).astype(int)
    df_health = pd.DataFrame({
        "blood_pressure": bp,
        "bmi": bmi,
        "glucose_level": glucose,
        "high_risk": high_risk
    })
    df_health.to_csv(DATASETS_DIR / "patient_health_screening.csv", index=False)

    # 4. Housing Market Prices (Regression)
    sqft = np.random.randint(950, 3600, n)
    beds = np.random.randint(1, 5, n)
    lot_size = np.random.randint(2200, 8500, n)
    noise_house = np.random.normal(0, 22000, n)
    price = (sqft * 175) + (beds * 24000) + (lot_size * 14) + 35000 + noise_house
    price = np.maximum(80000, price).round(2)
    df_housing = pd.DataFrame({
        "square_feet": sqft,
        "bedrooms": beds,
        "lot_size": lot_size,
        "price": price
    })
    df_housing.to_csv(DATASETS_DIR / "housing_market_prices.csv", index=False)

    # 5. Vehicle Resale Valuation (Regression)
    car_age = np.random.randint(1, 15, n)
    mileage_k = (car_age * np.random.uniform(10.0, 18.0, n)).round(1)
    engine_hp = np.random.choice([120, 150, 180, 220, 280, 340], n)
    noise_car = np.random.normal(0, 1800, n)
    car_price = 38000 - (car_age * 1950) - (mileage_k * 85) + (engine_hp * 45) + noise_car
    car_price = np.maximum(2500, car_price).round(2)
    df_car = pd.DataFrame({
        "vehicle_age": car_age,
        "mileage_k": mileage_k,
        "horsepower": engine_hp,
        "resale_price": car_price
    })
    df_car.to_csv(DATASETS_DIR / "vehicle_resale_valuation.csv", index=False)

    # 6. Advertising Revenue (Regression)
    tv_spend = np.random.uniform(5.0, 80.0, n).round(2)
    digital_spend = np.random.uniform(10.0, 95.0, n).round(2)
    promo_events = np.random.randint(1, 8, n)
    noise_rev = np.random.normal(0, 15.0, n)
    revenue_k = 40.0 + (tv_spend * 0.85) + (digital_spend * 1.45) + (promo_events * 6.5) + noise_rev
    revenue_k = np.maximum(20.0, revenue_k).round(2)
    df_ad = pd.DataFrame({
        "tv_spend_k": tv_spend,
        "digital_spend_k": digital_spend,
        "promo_events": promo_events,
        "sales_revenue_k": revenue_k
    })
    df_ad.to_csv(DATASETS_DIR / "advertising_revenue_forecast.csv", index=False)

    print(f"Generated 6 realistic datasets in '{DATASETS_DIR}/':")
    for f in DATASETS_DIR.glob("*.csv"):
        print(f" - {f.name} ({len(pd.read_csv(f))} rows)")

if __name__ == "__main__":
    generate_all_datasets()

