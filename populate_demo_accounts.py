import os
import uuid
import random
import io
import csv
import numpy as np
import pandas as pd
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from webui.models import Dataset, Run, RunBatch
from webui.standins.datasets import validate_csv
from webui.standins.runs import _execute_in_worker

PASSWORD = "PresentationPass123!"

ALL_USERS = [
    {"username": "pranav", "first_name": "Pranav", "last_name": "R P", "is_admin": True},
    {"username": "alice_chen", "first_name": "Alice", "last_name": "Chen", "is_admin": False},
    {"username": "bob_martinez", "first_name": "Bob", "last_name": "Martinez", "is_admin": False},
    {"username": "charlie_smith", "first_name": "Charlie", "last_name": "Smith", "is_admin": False},
    {"username": "diana_ross", "first_name": "Diana", "last_name": "Ross", "is_admin": False},
    {"username": "ethan_hunt", "first_name": "Ethan", "last_name": "Hunt", "is_admin": False},
    {"username": "fiona_gallagher", "first_name": "Fiona", "last_name": "Gallagher", "is_admin": False},
    {"username": "george_clark", "first_name": "George", "last_name": "Clark", "is_admin": False},
    {"username": "hannah_abbott", "first_name": "Hannah", "last_name": "Abbott", "is_admin": False},
    {"username": "ian_wright", "first_name": "Ian", "last_name": "Wright", "is_admin": False},
    {"username": "julia_roberts", "first_name": "Julia", "last_name": "Roberts", "is_admin": False},
    {"username": "demo", "first_name": "Demo", "last_name": "User", "is_admin": True},
]

# Generate realistic, natural classification dataset with non-trivial boundary
def generate_classification_dataset():
    np.random.seed(28)
    n = 100
    age = np.random.randint(21, 68, n)
    monthly_charges = np.random.uniform(28.0, 115.0, n).round(2)
    tenure_months = np.random.randint(1, 65, n)
    z1 = -1.8 + (0.04 * age) + (0.038 * monthly_charges) - (0.052 * tenure_months) + np.random.normal(0, 0.85, n)
    churn = (1 / (1 + np.exp(-z1)) > 0.5).astype(int)
    
    df = pd.DataFrame({
        "age": age,
        "monthly_charges": monthly_charges,
        "tenure_months": tenure_months,
        "churned": churn
    })
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    return "customer_churn_analysis.csv", csv_bytes, "churned", ["age", "monthly_charges", "tenure_months"]

# Generate realistic regression dataset with natural variance
def generate_regression_dataset():
    np.random.seed(42)
    n = 100
    sqft = np.random.randint(950, 3600, n)
    beds = np.random.randint(1, 5, n)
    lot_size = np.random.randint(2200, 8500, n)
    noise_house = np.random.normal(0, 22000, n)
    price = (sqft * 175) + (beds * 24000) + (lot_size * 14) + 35000 + noise_house
    price = np.maximum(80000, price).round(2)
    
    df = pd.DataFrame({
        "square_feet": sqft,
        "bedrooms": beds,
        "lot_size": lot_size,
        "price": price
    })
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    return "housing_market_prices.csv", csv_bytes, "price", ["square_feet", "bedrooms", "lot_size"]

CLASSIFICATION_ALGOS = [
    "random_forest",
    "decision_tree",
    "logistic_regression",
    "svm",
    "knn"
]

REGRESSION_ALGOS = [
    "linear_regression",
    "random_forest_regressor",
    "decision_tree_regressor"
]

def main():
    print("Populating realistic, non-100% benchmark datasets across accounts...\n")
    
    cls_name, cls_bytes, cls_target, cls_features = generate_classification_dataset()
    reg_name, reg_bytes, reg_target, reg_features = generate_regression_dataset()

    for uinfo in ALL_USERS:
        uname = uinfo["username"]
        user, _ = User.objects.get_or_create(username=uname)
        user.first_name = uinfo["first_name"]
        user.last_name = uinfo["last_name"]
        user.email = f"{uname}@example.com"
        user.is_staff = uinfo["is_admin"]
        user.is_superuser = uinfo["is_admin"]
        user.set_password(PASSWORD if uname != "demo" else "demo-pass-123")
        user.save()
        
        # Clean previous runs and datasets for this user
        Run.objects.filter(owner=user).delete()
        RunBatch.objects.filter(owner=user).delete()
        for d in Dataset.objects.filter(owner=user):
            d.file.delete(save=False)
            d.delete()

        print(f"User: {uname} ({user.first_name} {user.last_name})")

        # 1. Classification Dataset (100 rows, realistic varied accuracy)
        up_cls = ContentFile(cls_bytes, name=cls_name)
        prof_cls = validate_csv(up_cls)
        up_cls.seek(0)
        d_cls = Dataset.objects.create(
            owner=user,
            original_name=cls_name,
            file=up_cls,
            rows=prof_cls["rows"],
            column_count=prof_cls["column_count"],
            profile=prof_cls
        )
        for algo in CLASSIFICATION_ALGOS:
            cfg = {
                "dataset_id": str(d_cls.id),
                "target_column": cls_target,
                "feature_columns": cls_features,
                "imputation": None,
                "encoding": None,
                "scaling": None,
                "split_ratio": 0.8,
                "random_seed": 42,
                "algorithm": algo,
                "hyperparameters": {}
            }
            r = Run.objects.create(
                job_key="r-" + uuid.uuid4().hex[:8],
                owner=user,
                dataset=d_cls,
                run_config=cfg,
                state=Run.QUEUED
            )
            _execute_in_worker(r.job_key, queue_s=0, run_s=0)

        # 2. Regression Dataset (100 rows, realistic varied R2 and RMSE)
        up_reg = ContentFile(reg_bytes, name=reg_name)
        prof_reg = validate_csv(up_reg)
        up_reg.seek(0)
        d_reg = Dataset.objects.create(
            owner=user,
            original_name=reg_name,
            file=up_reg,
            rows=prof_reg["rows"],
            column_count=prof_reg["column_count"],
            profile=prof_reg
        )
        for algo in REGRESSION_ALGOS:
            cfg = {
                "dataset_id": str(d_reg.id),
                "target_column": reg_target,
                "feature_columns": reg_features,
                "imputation": None,
                "encoding": None,
                "scaling": None,
                "split_ratio": 0.8,
                "random_seed": 42,
                "algorithm": algo,
                "hyperparameters": {}
            }
            r = Run.objects.create(
                job_key="r-" + uuid.uuid4().hex[:8],
                owner=user,
                dataset=d_reg,
                run_config=cfg,
                state=Run.QUEUED
            )
            _execute_in_worker(r.job_key, queue_s=0, run_s=0)

        print(f"  ✓ Created 2 realistic datasets & 8 differentiated models for {uname}")

    print("\nSUCCESS: All accounts now have realistic, non-100% benchmark results!")

if __name__ == "__main__":
    main()
