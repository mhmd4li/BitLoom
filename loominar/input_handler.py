import os

def get_user_inputs(cli_defaults=None):
    if cli_defaults is None:
        cli_defaults = {}

    def get_value(prompt_text, key, default=None):
        if cli_defaults.get(key):
            return cli_defaults[key]
        value = input(prompt_text).strip()
        return value or default

    # Gather inputs
    sonar_url = get_value("Enter SonarQube server URL (e.g., http://localhost:9000): ", "url")
    sonar_token = get_value("Enter SonarQube API token: ", "token")
    project_key = get_value("Enter SonarQube project key: ", "project")

    output_format = get_value("Enter output format (word / excel / csv): ", "format", "excel").lower()
    verbosity = int(cli_defaults.get("verbosity", 2))

    # Default output dir → Documents/Loominar
    user_documents = os.path.join(os.path.expanduser("~"), "Documents")
    default_dir = os.path.join(user_documents, "Loominar")

    output_dir = get_value(f"Enter output directory (leave blank for {default_dir}): ", "output", default_dir)
    os.makedirs(output_dir, exist_ok=True)

    return {
        "sonar_url": sonar_url,
        "sonar_token": sonar_token,
        "project_key": project_key,
        "format": output_format,
        "verbosity": verbosity,
        "output_dir": output_dir,
        "no_confirm": cli_defaults.get("no_confirm", False),
    }

