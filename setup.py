"""
Package setup for Qwen Code API Server
"""
from setuptools import setup, find_packages

setup(
    name="qwen-code-api-server",
    version="1.0.0",
    description="Modular Qwen Code API Server with FastAPI",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "aiohttp>=3.8.0",
    ],
    include_package_data=True,
    package_data={
        "": ["templates/*.html", "static/*"],
    },
    entry_points={
        "console_scripts": [
            "qwen-api-server=src.main:main",
        ],
    },
)