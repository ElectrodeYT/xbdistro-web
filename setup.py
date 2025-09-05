from distutils.core import setup

setup(
    name='xbdistro_tools',
    version='0.0.1',
    packages=['xbdistro_tools', 'xbdistro_tools.upstream_fetchers'],
    url='',
    license='',
    author='alexander',
    author_email='',
    description='',
    entry_points={
        'console_scripts': [
            'xbdistro_tools=xbdistro_tools.cli:main',
            'xbdistro_cron=xbdistro_tools.cron:main'
        ]
    }
)
