# Large Image Dataset into Label Studio

## Project Overview

This project aims to develop an automated workflow for handling large aerial survey images using SAHI (Slicing Aided Hyper Inference), YOLO object detection, and Label Studio.

## Objective

Slice large aerial images into overlapping tiles, detect objects using a trained YOLO model, merge predictions into the original image coordinates, remove duplicate bounding boxes, and upload the resulting predictions to Label Studio for review.

## Technologies Used

- Python
- SAHI
- Ultralytics YOLO
- Label Studio
- Label Studio REST API
- PyTorch

## Proposed Workflow

1. Obtain the original large aerial image dataset.
2. Split the dataset into training, validation, and testing subsets.
3. Slice the large images into overlapping tiles using SAHI.
4. Upload training and validation tiles to Label Studio.
5. Annotate the training and validation images.
6. Train the YOLO object detection model.
7. Validate the trained model.
8. Generate bounding-box predictions on the held-out, unannotated testing images.
9. Merge tile-level predictions into original-image coordinates.
10. Remove overlapping duplicate detections.
11. Upload merged predictions to Label Studio through its API.
12. Review and correct predictions.
13. Document the workflow and results.

## Implementation Notes

The pipeline uses overlapping image tiles to help detect small objects in high-resolution aerial imagery.

Bounding boxes must be converted from tile coordinates to original-image coordinates before uploading the merged predictions to Label Studio.

## Project Status

Work in progress. Implementation scripts, validation results, and example runs will be documented as development continues.
