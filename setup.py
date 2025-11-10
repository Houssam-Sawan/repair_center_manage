from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

from repair_center_manager import __version__ as version

setup(
    name="repair_center_manager",
    version=version,
    description="Repair Center Management App",
    author="Houssam",
    author_email="eng.houssam.sawan@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
