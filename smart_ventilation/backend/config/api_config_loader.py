import yaml

def load_api_config(config_file_path):
    with open(config_file_path, "r") as file:
        api_config = yaml.safe_load(file)
    return api_config
