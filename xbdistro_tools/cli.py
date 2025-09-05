import os
import xbstrap.base
import argparse
from pprint import pprint
from xbdistro_tools.upstream_fetchers.nixos import NixOSVersionProvider
from xbdistro_tools.db import PackageDatabase

class SplitArgs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.split(','))

def do_source(args, db: PackageDatabase | None, dist_source, done_sources):
    if dist_source.name in done_sources:
        return

    try:
        version = dist_source.version
    except xbstrap.exceptions.RollingIdUnavailableError:
        version = 'RollingIDUnavailable'
    except AssertionError:
        print(f'{dist_source.name}: <AssertionFailed>')
        return

    version_str = f'{dist_source.name}: {version}'

    if args.export_db:
        db.add_source_version(dist_source.name, version, 'local')
        # Add the metadata from each package using this source

    if args.upstream == 'nixos':
        provider = NixOSVersionProvider()
        upstream_version = provider.get_version(dist_source.name)
        if upstream_version:
            version_str += f' (upstream: {upstream_version})'
            if args.export_db:
                db.add_source_version(dist_source.name, upstream_version, 'nixos')

    if args.print_version:
        print(version_str)

    done_sources.append(dist_source.name)

def do_package(args, db: PackageDatabase | None, dist_package: xbstrap.base.TargetPackage, distro, done_packages):
    if dist_package.name in done_packages:
        return

    do_source(args, db, distro.get_source(dist_package.source), done_packages)

    if args.export_db:
        maintainer = None
        homepage_url = None
        license = None
        category = None
        summary = None
        description = None


        if hasattr(dist_package, '_subpkg_yml') and dist_package._subpkg_yml:
            package_yml = dist_package._subpkg_yml
        else:
            package_yml = dist_package._this_yml

        if 'metadata' in package_yml:
            metadata_yml = package_yml['metadata']
            if 'maintainer' in metadata_yml:
                maintainer = metadata_yml['maintainer']
            if 'website' in metadata_yml:
                homepage_url = metadata_yml['website']
            if 'spdx' in metadata_yml:
                license = metadata_yml['spdx']
            if 'categories' in metadata_yml:
                category = ', '.join(metadata_yml['categories'])
            if 'summary' in metadata_yml:
                summary = metadata_yml['summary']
            if 'description' in metadata_yml:
                description = metadata_yml['description']

        db.add_package_metadata(dist_package.source, dist_package.name,
                                maintainer=maintainer,
                                homepage_url=homepage_url,
                                license=license,
                                category=category,
                                summary=summary,
                                description=description)

    done_packages.append(dist_package.name)

def main():
    parser = argparse.ArgumentParser(description='Check versions of sources in xbstrap distribution')
    parser.add_argument('--path', default='bootstrap-managarm', help='Path to xbstrap distribution')
    parser.add_argument('--upstream', choices=['nixos'], help='Compare versions with upstream source')
    parser.add_argument('--export-db', metavar='DB_PATH', help='Export versions to a SQLite database')
    parser.add_argument('--all-sources', action='store_true', help='Check all available sources')
    parser.add_argument('--all-packages', action='store_true', help='Check all available packages')
    parser.add_argument('--print-version', action='store_true', help='Print version information')
    parser.add_argument('--sources', action=SplitArgs, help='List of sources to check')
    parser.add_argument('--packages', action=SplitArgs, help='List of packages to check')
    args = parser.parse_args()

    distro = xbstrap.base.Config(path=args.path, changed_source_root=args.path)

    done_sources = []
    done_packages = []

    if args.export_db:
        db = PackageDatabase(args.export_db)
    else:
        db = None

    sources = []
    if args.all_sources:
        sources = distro.all_sources()
    else:
        if args.sources is not None:
            for source in args.sources:
                try:
                    sources.append(distro.get_source(source))
                except KeyError:
                    print(f'{source}: doesn\'t exist locally')
                    continue

    for dist_source in sources:
        do_source(args, db, dist_source, done_sources)

    packages = []
    if args.all_packages:
        packages = distro.all_pkgs()
    else:
        if args.packages is not None:
            for package in args.packages:
                try:
                    packages.append(distro.get_target_pkg(package))
                except KeyError:
                    print(f'{package}: doesn\'t exist locally')
                    continue

    for dist_package in packages:
        do_package(args, db, dist_package, distro, done_packages)

    if args.export_db:
        db.close()

