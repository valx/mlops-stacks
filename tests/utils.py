import os
import pathlib
import pytest
import json
import subprocess
from functools import wraps

RESOURCE_TEMPLATE_ROOT_DIRECTORY = str(pathlib.Path(__file__).parent.parent)

AZURE_DEFAULT_PARAMS = {
    "input_setup_cicd_and_project": "CICD_and_Project",
    "input_root_dir": "my-mlops-project",
    "input_project_name": "my-mlops-project",
    "input_cloud": "azure",
    "input_cicd_platform": "github_actions",
    "input_databricks_test_workspace_host": "https://adb-xxxx.xx.azuredatabricks.net",
    "input_databricks_staging_workspace_host": "https://adb-xxxx.xx.azuredatabricks.net",
    "input_databricks_prod_workspace_host": "https://adb-xxxx.xx.azuredatabricks.net",
    "input_default_branch": "main",
    "input_release_branch": "release",
    "input_read_user_group": "users",
    "input_include_feature_store": "no",
    "input_include_mlflow_recipes": "no",
    "input_include_models_in_unity_catalog": "no",
    "input_schema_name": "schema_name",
    "input_unity_catalog_read_user_group": "account users",
    "input_inference_table_name": "dummy.schema.table",
}

AWS_DEFAULT_PARAMS = {
    **AZURE_DEFAULT_PARAMS,
    "input_cloud": "aws",
    "input_databricks_test_workspace_host": "https://your-staging-workspace.cloud.databricks.com",
    "input_databricks_staging_workspace_host": "https://your-staging-workspace.cloud.databricks.com",
    "input_databricks_prod_workspace_host": "https://your-prod-workspace.cloud.databricks.com",
}

GCP_DEFAULT_PARAMS = {
    **AZURE_DEFAULT_PARAMS,
    "input_cloud": "gcp",
    "input_databricks_test_workspace_host": "https://your-staging-workspace.gcp.databricks.com",
    "input_databricks_staging_workspace_host": "https://your-staging-workspace.gcp.databricks.com",
    "input_databricks_prod_workspace_host": "https://your-prod-workspace.gcp.databricks.com",
}


def parametrize_by_cloud(fn):
    @wraps(fn)
    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


def parametrize_by_project_generation_params(fn):
    @pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
    @pytest.mark.parametrize(
        "cicd_platform",
        [
            "github_actions",
            "github_actions_for_github_enterprise_servers",
            "azure_devops",
        ],
    )
    @pytest.mark.parametrize(
        "setup_cicd_and_project,include_feature_store,include_mlflow_recipes,include_models_in_unity_catalog",
        [
            ("CICD_and_Project", "no", "no", "no"),
            ("CICD_and_Project", "no", "no", "yes"),
            ("CICD_and_Project", "no", "yes", "no"),
            ("CICD_and_Project", "yes", "no", "no"),
            ("CICD_and_Project", "yes", "no", "yes"),
            ("Project_Only", "no", "no", "no"),
            ("Project_Only", "no", "no", "yes"),
            ("Project_Only", "no", "yes", "no"),
            ("Project_Only", "yes", "no", "no"),
            ("Project_Only", "yes", "no", "yes"),
            ("CICD_Only", "no", "no", "no"),
        ],
    )
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


@pytest.fixture
def generated_project_dir(
    tmpdir,
    databricks_cli,
    cloud,
    cicd_platform,
    setup_cicd_and_project,
    include_feature_store,
    include_mlflow_recipes,
    include_models_in_unity_catalog,
):
    params = {
        "input_setup_cicd_and_project": setup_cicd_and_project,
        "input_root_dir": "my-mlops-project",
        "input_cloud": cloud,
    }
    if setup_cicd_and_project != "Project_Only":
        params.update(
            {
                "input_cicd_platform": cicd_platform,
                "input_databricks_staging_workspace_host": "https://adb-3214.67.azuredatabricks.net",
                "input_databricks_prod_workspace_host": "https://adb-345.89.azuredatabricks.net",
                "input_default_branch": "main",
                "input_release_branch": "release",
            }
        )
    if setup_cicd_and_project != "CICD_Only":
        params.update(
            {
                "input_project_name": "my-mlops-project",
                "input_include_feature_store": include_feature_store,
                "input_include_mlflow_recipes": include_mlflow_recipes,
                "input_read_user_group": "users",
                "input_include_models_in_unity_catalog": include_models_in_unity_catalog,
                "input_schema_name": "schema_name",
                "input_unity_catalog_read_user_group": "account users",
                "input_inference_table_name": "dummy.schema.table",
            }
        )
    generate(tmpdir, databricks_cli, params)
    return tmpdir


def read_workflow(tmpdir):
    return (tmpdir / "my-mlops-project" / ".github/workflows/run-tests.yml").read_text(
        "utf-8"
    )


def markdown_checker_configs(tmpdir):
    markdown_checker_config_dict = {
        "ignorePatterns": [
            {"pattern": "http://127.0.0.1:5000"},
            {"pattern": "https://adb-3214.67.azuredatabricks.net*"},
            {"pattern": "https://adb-345.89.azuredatabricks.net*"},
        ],
        "httpHeaders": [
            {
                "urls": ["https://docs.github.com/"],
                "headers": {"Accept-Encoding": "zstd, br, gzip, deflate"},
            },
        ],
    }

    file_name = "checker-config.json"

    with open(tmpdir / "my-mlops-project" / file_name, "w") as outfile:
        json.dump(markdown_checker_config_dict, outfile)


def generate(directory, databricks_cli, context):
    if context.get("input_cloud") == "aws":
        default_params = AWS_DEFAULT_PARAMS
    elif context.get("input_cloud") == "gcp":
        if context.get("input_include_models_in_unity_catalog") == "yes":
            return
        default_params = GCP_DEFAULT_PARAMS
    else:
        default_params = AZURE_DEFAULT_PARAMS
    params = {
        **default_params,
        **context,
    }
    json_string = json.dumps(params)
    config_file = directory / "config.json"
    config_file.write(json_string)
    subprocess.run(
        f"echo dapi123 | {databricks_cli} configure --host https://123",
        shell=True,
        check=True,
    )
    subprocess.run(
        f"{databricks_cli} bundle init {RESOURCE_TEMPLATE_ROOT_DIRECTORY} --config-file {config_file} --output-dir {directory}",
        shell=True,
        check=True,
    )


@pytest.fixture(scope="session")
def databricks_cli(tmp_path_factory):
    # create tools dir
    tool_dir = tmp_path_factory.mktemp("tools")
    # copy script and make it executable
    install_script_path = os.path.join(os.path.dirname(__file__), "install.sh")
    # download databricks cli
    databricks_cli_dir = tool_dir / "databricks_cli"
    databricks_cli_dir.mkdir()
    subprocess.run(
        ["bash", install_script_path, databricks_cli_dir],
        capture_output=True,
        text=True,
    )

    yield f"{databricks_cli_dir}/databricks"
    # no need to remove the files as they are in test temp dir


def paths(directory):
    paths = list(pathlib.Path(directory).glob("**/*"))
    paths = [r.relative_to(directory) for r in paths]
    return {str(f) for f in paths if str(f) != "."}
