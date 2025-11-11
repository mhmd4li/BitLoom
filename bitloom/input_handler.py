import os

def get_user_inputs():
    """
    Collects and validates basic user inputs required for SonarQube report generation.
    Returns a dictionary of configuration parameters.
    """

    print("🧶 BitLoom — SonarQube Report Exporter\n")

    sonar_url = input("Enter SonarQube server URL (e.g., http://localhost:9000): ").strip()
    if not sonar_url:
        raise ValueError("SonarQube URL cannot be empty.")

    sonar_token = input("Enter SonarQube API token: ").strip()
    if not sonar_token:
        raise ValueError("SonarQube API token cannot be empty.")

    project_key = input("Enter SonarQube project key: ").strip()
    if not project_key:
        raise ValueError("Project key cannot be empty.")

    fmt = input("Enter output format (word / excel / csv): ").strip().lower()
    if fmt not in ["word", "excel", "csv"]:
        raise ValueError("Invalid format. Must be 'word', 'excel', or 'csv'.")

    output_dir = input("Enter output directory (leave blank for ./Reports): ").strip()
    if not output_dir:
        output_dir = "./Reports"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    verbosity = input("Select verbosity level (1=Low, 2=Medium, 3=High): ").strip()
    verbosity = int(verbosity) if verbosity.isdigit() and 1 <= int(verbosity) <= 3 else 2

    config = {
        "sonar_url": sonar_url,
        "sonar_token": sonar_token,
        "project_key": project_key,
        "output_dir": output_dir,
        "format": fmt,
        "verbosity": verbosity
    }

    return config


if __name__ == "__main__":
    cfg = get_user_inputs()
    print("\n✅ Configuration Loaded:")
    for k, v in cfg.items():
        if k == "sonar_token":
            print(f"  {k}: {'*' * 8}")  # mask token
        else:
            print(f"  {k}: {v}")
