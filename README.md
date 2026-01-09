# PowerPoint to Word Converter

A Streamlit web application that converts PowerPoint presentations to Word documents.

## Features

- Upload PowerPoint files (.pptx)
- Converts all slides with their text content
- Preserves slide structure with headings
- Handles bulleted lists and tables
- Download the converted Word document

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the Streamlit app:
```bash
streamlit run app.py
```

The app will open in your browser. Upload a PowerPoint file and click the download button to get the converted Word document.

## How it Works

The app uses:
- **Streamlit** for the web interface
- **python-pptx** to read PowerPoint files
- **python-docx** to create Word documents

Each slide is converted to a section in the Word document with appropriate formatting.
