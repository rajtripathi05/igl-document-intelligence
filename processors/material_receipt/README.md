# Material Receipt Processor

## Purpose

This folder is reserved for the future enterprise material_receipt document processor.
It is scaffolding only and is not connected to the running application yet.

## Expected Files

- processor.py: future processor entry point and metadata.
- validator.py: future document-specific validation rules.
- exporter.py: future export generation logic.
- classification.json: future classification keywords and routing hints.
- prompts/system_prompt.txt: future AI system instructions.
- prompts/extraction_prompt.txt: future AI extraction instructions.
- schema/schema.json: future canonical JSON schema.
- templates/: future Excel or ERP templates.
- samples/: future sample PDFs and images for testing.

## Folder Usage

Keep all files for this document type inside this folder when the enterprise
processor migration begins. Do not move existing shared prompts, schemas,
templates, or samples into this folder until the migration task explicitly does
so.

## Examples

Future examples may include sample source documents, expected JSON output,
validation scenarios, and export mapping notes for Material Receipt.
