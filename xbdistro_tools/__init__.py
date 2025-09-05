import requests


def download_file(url, destination_path):
    """Downloads a file from the given URL and saves it to the specified path.

    Args:
        url (str): URL of the file to download
        destination_path (str): Path where the file should be saved

    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192

        with open(destination_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    file.write(chunk)

        return True
    except requests.RequestException as e:
        print(f"Error downloading file: {e}")
        return False
