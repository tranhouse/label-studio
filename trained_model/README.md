\# Trained YOLO Model



This folder contains the trained YOLO11n model for the

Large Image Dataset into Label Studio project.



\## Model Files



\- best.pt: Best model weights from YOLO training.

\- data.yaml: Dataset configuration and class names.

\- dataset\_splits/: Lists of original images assigned to

&#x20; training, validation, and testing.



\## Model Configuration



\- Model: YOLO11n

\- Training epochs: 30

\- Image size: 640 x 640

\- Batch size: 8

\- Device: CPU



\## Object Classes



0 - Car

1 - Person

2 - Ship



\## Validation



The model was trained using 43 annotated training tiles

and 25 annotated validation tiles.



The next step is to connect the trained model to Label Studio

through the Docker-based YOLO ML backend and retrieve

predictions on validation images.



\## Notes



The original dataset images are not included in this repository.



The path in data.yaml must point to the appropriate local

dataset directory when used for training or evaluation.

