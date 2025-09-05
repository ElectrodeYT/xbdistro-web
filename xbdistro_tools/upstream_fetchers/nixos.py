from xbdistro_tools.upstream_fetchers import *
from xbdistro_tools import download_file
import os
import json
from datetime import datetime, timedelta
from pprint import pprint

class NixOSVersionProvider(UpstreamVersionProvider):
    _packages_data = None
    def __init__(self, download='https://nixos.org/channels/nixpkgs-unstable/packages.json.br',
                 cache_location=None, always_redownload=False):
        self.download = download
        self.cache_location = cache_location
        self.always_redownload = always_redownload

    def _download_package_json(self):
        """Downloads and caches the NixOS package JSON file."""
        output_path = self.cache_location if self.cache_location else "nixos_packages.json"

        should_download = self.always_redownload
        if os.path.exists(output_path):
            file_time = datetime.fromtimestamp(os.path.getmtime(output_path))
            if datetime.now() - file_time > timedelta(days=1):
                should_download = True
        else:
            should_download = True

        if should_download:
            download_file(self.download, output_path)
        return output_path

    def _read_packages(self):
        """Reads and parses the NixOS package JSON file."""
        json_path = self._download_package_json()
        with open(json_path, 'r') as f:
            NixOSVersionProvider._packages_data = json.load(f)
        return NixOSVersionProvider._packages_data

    @property
    def packages_data(self):
        """Returns the parsed nixos package JSON file."""
        if NixOSVersionProvider._packages_data is None:
            return self._read_packages()
        return NixOSVersionProvider._packages_data

    @property
    def _packages_json(self):
        return self.packages_data['packages']

    def _package_json(self, package):
        return self.packages_data['packages'][package]

    def get_version(self, package):
        """Returns the version of the given nixos package."""
        if package not in self._packages_json:
            return None

        return self._package_json(package)['version']


