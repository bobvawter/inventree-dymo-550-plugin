# -*- coding: utf-8 -*-

import setuptools

from inventree_dymo.version import DYMO_PLUGIN_VERSION

with open('README.md', encoding='utf-8') as f:
    long_description = f.read()


setuptools.setup(
    author="bobvawter",
    author_email="bob@vawter.org",
    description="Dymo 550 Label printer driver plugin for InvenTree",
    keywords="inventree dymo",
    include_package_data=True,
    install_requires=[],
    license="MIT",
    long_description=long_description,
    long_description_content_type='text/markdown',
    name="inventree-dymo-550-plugin",
    packages=setuptools.find_packages(),
    python_requires=">=3.9",
    setup_requires=[],
    url="https://github.com/bobvawter/inventree-dymo-550-driver",
    version=DYMO_PLUGIN_VERSION,
    entry_points={
        "inventree_plugins": [
            "InvenTreeDymo550Plugin = inventree_dymo.InvenTreeDymo550Plugin:InvenTreeDymo550Plugin"
        ]
    },
)
