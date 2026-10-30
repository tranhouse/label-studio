\# YOLO ML Backend - Docker Setup



\## Overview



This folder contains the Docker configuration and Python code used to connect a trained YOLO object detection model to Label Studio.



The backend allows Label Studio to request object detection predictions and display them as pre-annotations.



\## Requirements



\- Docker Desktop with Docker Compose

\- Label Studio

\- Trained YOLO model (`best.pt`)

\- Label Studio Legacy API Token



\## Setup



1\. Clone the `OCDS-AI-Student-Deliverables` repository.

2\. Navigate to `Large-Image-Dataset-Label-Studio/yolo\_ml\_backend`.

3\. Copy `../trained\_model/best.pt` into `models/` and rename it `my\_model.pt`.

4\. Create a local `.env` file containing:



&#x20;  `LABEL\_STUDIO\_API\_KEY=<YOUR\_LEGACY\_API\_TOKEN>`



&#x20;  `TEST\_ENV=false`



5\. Ensure Label Studio is running on port 8080.

6\. Build and start the backend:



&#x20;  `docker compose up -d --build`



7\. Verify the backend is available at `http://localhost:9090`.

8\. In Label Studio, open the project settings, select Machine Learning, and connect the backend using `http://localhost:9090`.



\## Generate Predictions



1\. Upload images into a Label Studio project.

2\. Confirm the labeling configuration uses the same classes as the model.

3\. Select the uploaded tasks.

4\. Choose \*\*Actions → Retrieve Predictions\*\*.

5\. Open a task to review the detected bounding boxes.



\## Notes



\- The backend uses `host.docker.internal:8080` to access Label Studio running on the same Windows computer.

\- The model is mounted into the Docker container using `./models:/app/models`.

\- Do not commit `.env`, API tokens, or passwords to GitHub.

\- The configuration was previously tested locally on Windows. Other environments may require changes to networking and Docker settings.

