from setuptools import setup, find_packages

# Read the contents of the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="puregen",
    version="0.1.0",
    author="MushroomSquad",
    author_email="donsudak@gmail.com",
    description="Give your code the freedom to move",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MushroomSquad/puregen",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "annotated-types==0.7.0",
        "argcomplete==3.5.3",
        "black==25.1.0",
        "click==8.1.8",
        "datamodel-code-generator==0.28.1",
        "genson==1.3.0",
        "graphql-core==3.2.6",
        "inflect==5.6.2",
        "isort==6.0.0",
        "Jinja2==3.1.5",
        "markdown-it-py==3.0.0",
        "MarkupSafe==3.0.2",
        "mdurl==0.1.2",
        "mypy-extensions==1.0.0",
        "packaging==24.2",
        "pathspec==0.12.1",
        "platformdirs==4.3.6",
        "pydantic==2.10.6",
        "pydantic_core==2.27.2",
        "Pygments==2.19.1",
        "PyYAML==6.0.2",
        "rich==13.9.4",
        "setuptools==75.8.0",
        "shellingham==1.5.4",
        "typer==0.15.1",
        "typing_extensions==4.12.2",
    ],
    entry_points={
        "console_scripts": [
            "puregen = puregen.__main__:app",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)

