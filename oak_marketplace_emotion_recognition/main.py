import os

import cv2
import numpy as np
import skvideo.io
from emotion_recognition_retail import InferenceModel, process_frame
from modelplace_api.visualization import draw_emotion_recognition_one_frame
from args_parser import parse_args
from utils import EllipseGraphsCollector, overlay_image_alpha, place_class_names_and_percents

X_OFFSET = 5
Y_OFFSET = 20


def build_model(model_path):
    model = InferenceModel(model_path=model_path)
    model.model_load()
    model.add_cam_to_pipeline()
    return model


def main(args):
    model_path = os.path.join(args.root_model_path, "checkpoint")
    model = build_model(model_path)
    input_width, input_height = model.get_input_shapes()
    graphs_collector = EllipseGraphsCollector()
    proceed = True
    visualization_results = []
    overlay = cv2.imread("overlay_450x450.png", cv2.IMREAD_UNCHANGED)

    while proceed:
        image = np.ascontiguousarray(
            model.get_frame_from_camera()
                .reshape((3, input_height, input_width))
                .transpose(1, 2, 0),
        )
        ret, proceed, _ = process_frame(image, model, visualization_func=None)
        if ret:
            class_name = ret[0].emotions[0].class_name
            graphs_collector.update_graph(class_name)
        image = cv2.resize(image, (450, 450))
        vis_result = draw_emotion_recognition_one_frame(image, ret)

        start_x, start_y = np.clip(vis_result.shape[0] - graphs_collector.graphs_size, 0, vis_result.shape[0]) , \
                               np.clip(vis_result.shape[1] - graphs_collector.graphs_size - Y_OFFSET, 0, vis_result.shape[0])
        alpha_mask_overlay = overlay[:, :, 3] / 255.0
        overlay_background = overlay[..., :3]
        overlay_image_alpha(vis_result, overlay_background, 0, 0, alpha_mask_overlay)
        for emotion, ellipse_graph in graphs_collector.graphs.items():
            percent = graphs_collector.get_current_emotion_percent(emotion)
            text = f'{emotion.upper()} - {percent}%'
            vis_result = place_class_names_and_percents(vis_result,[start_x, int(vis_result.shape[1] - Y_OFFSET / 2)],
                                                        text)
            alpha_mask = ellipse_graph.alpha_mask
            overlay_image_alpha(vis_result, ellipse_graph.graph, start_x , start_y, alpha_mask)
            start_x = np.clip(start_x - graphs_collector.graphs_size - X_OFFSET, 0, vis_result.shape[0])
        visualization_results.append(vis_result)

        if args.visualization:
            cv2.imshow('result', vis_result)
            if cv2.waitKey(1) == ord("q"):
                cv2.destroyAllWindows()
                proceed = False

    if args.output_video:
        FFMPEG_OUTPUT_DICT = {
            "-vcodec": "libx265",
            "-vf": "format=yuv420p",
            "-movflags": "+faststart",
        }
        writer = skvideo.io.FFmpegWriter(
            os.path.join(os.path.dirname(__file__), "inference_results.mp4"),
            outputdict=FFMPEG_OUTPUT_DICT,
        )
        for frame in visualization_results:
            writer.writeFrame(frame[:,:,::-1])
        writer.close()

    is_save = True if args.output_statistic else False
    graphs_collector.plot_statistic_result(is_save=is_save)
    if is_save:
        graphs_collector.dump_statistic_to_json()


if __name__ == "__main__":
    args = parse_args()
    main(args)
