# SAHI Pipeline — Handover Notes

## Included files
- run_sahi_inference.py — SAHI inference
- convert_to_labelstudio.py — prediction format conversion
- upload_sahi_predictions.py — Label Studio prediction upload script
- create_viewer_tiles.py — OpenSeadragon tile generation
- train_yolo.py — YOLO training
- train_test.py and prepare_person_dataset.py — experimental scripts
- sahi_results/ — example predictions for image 0793
- tiled_viewer/ — example deep-zoom viewer and tiles

## Verified
- SAHI prediction JSON generated for image 0793.
- Docker YOLO backend connected to local Label Studio.
- Predictions displayed for original validation images through the ML backend.
- OpenSeadragon image zooming and panning worked independently.

## Not yet verified
- Complete standalone SAHI-to-Label Studio prediction upload workflow.
- upload_sahi_predictions.py with the final Legacy API Token setup.
  The current script uses token refresh and Bearer authentication.
- OpenSeadragon prediction overlays.
- End-to-end prediction generation on sliced training images.

## Model setup
The trained model is stored in the repository under trained_model/best.pt.
The Docker backend uses a copy named models/my_model.pt.

Refer to yolo_ml_backend/README.md for Docker setup instructions.
Never commit API tokens or .env files.
