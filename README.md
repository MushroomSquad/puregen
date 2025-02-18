<div align="center">
  <img src="./logo.png" alt="Logo" width="364">
</div>

# puregen

**puregen – give your code the freedom to move.**

[![Issues](https://img.shields.io/github/issues/MushroomSquad/puregen)](https://github.com/MushroomSquad/puregen/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

---

## Overview

**puregen** is a lightweight wrapper built on top of [datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator) that resolves the issue of having all generated code dumped into a single file. Instead, puregen automatically organizes your code into well-structured folders and files, making your project much easier to maintain.

**Key Features:**
- **Automatic Structuring:** Divides generated code into logical modules and directories.
- **Seamless Imports:** Automatically generates the necessary import statements between files.
- **Efficient for Large Projects:** Ideal for projects with a vast number of models where managing a single file becomes cumbersome.

> **Note:** This is the first version of puregen and is still under active development. We welcome your feedback and suggestions!

---

## Getting Started

### Installation

Install puregen using pip:

```bash
pip install puregen
```

Or:

```bash
pip install git+https://github.com/MushroomSquad/puregen.git
```

## Simple Usage
You can generate models from a local file.
```bash
puregen --input "api.yaml" --input-file-type "openapi" 
```
