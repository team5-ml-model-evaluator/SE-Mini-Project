
from django import forms


MODEL_CHOICES = [
    ("LogisticRegression", "Logistic Regression"),
    ("DecisionTreeClassifier", "Decision Tree Classifier"),
    ("RandomForestClassifier", "Random Forest Classifier"),
    ("KNeighborsClassifier", "K-Nearest Neighbors"),
    ("SVC", "Support Vector Classifier"),
    ("LinearRegression", "Linear Regression"),
    ("DecisionTreeRegressor", "Decision Tree Regressor"),
    ("RandomForestRegressor", "Random Forest Regressor"),
]


class TrainingJobForm(forms.Form):
    dataset_name = forms.CharField(
        max_length=255,
        strip=True,
        help_text="Enter the name of the dataset to evaluate.",
    )

    model_name = forms.ChoiceField(
        choices=MODEL_CHOICES,
        help_text="Select a supported machine-learning model.",
    )

    configuration = forms.JSONField(
        required=False,
        initial=dict,
        help_text='Optional JSON configuration, e.g. {"random_state": 42}',
    )

    def clean_dataset_name(self):
        dataset_name = self.cleaned_data["dataset_name"]

        if not dataset_name:
            raise forms.ValidationError(
                "Dataset name cannot be empty."
            )

        return dataset_name

    def clean_configuration(self):
        configuration = self.cleaned_data.get("configuration")

        if configuration is None:
            return {}

        if not isinstance(configuration, dict):
            raise forms.ValidationError(
                "Configuration must be a JSON object."
            )

        return configuration
