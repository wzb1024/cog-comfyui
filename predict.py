import os
import shutil
import tarfile
import zipfile
import mimetypes
from typing import List
from cog import BasePredictor, Input, Path
from comfyui import ComfyUI
from weights_downloader import WeightsDownloader
from cog_model_helpers import optimise_images
from config import config


os.environ["DOWNLOAD_LATEST_WEIGHTS_MANIFEST"] = "false"
COMFYUI_INPUTS = "/src/input"
COMFYUI_OUTPUTS = "/src/output"
mimetypes.add_type("image/webp", ".webp")
OUTPUT_DIR = "/tmp/outputs"
INPUT_DIR = "/tmp/inputs"
COMFYUI_TEMP_OUTPUT_DIR = "ComfyUI/temp"
ALL_DIRECTORIES = [OUTPUT_DIR, INPUT_DIR, COMFYUI_TEMP_OUTPUT_DIR]


with open("workflow.json", "r") as file:
    EXAMPLE_WORKFLOW_JSON = file.read()

import os
import shutil

# 同步文件
def copy_files(src_folder, dest_folder):
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    if os.path.exists(src_folder):
        for item in os.listdir(src_folder):
            src_path = os.path.join(src_folder, item)
            dest_path = os.path.join(dest_folder, item)

            if os.path.isdir(src_path):
                # 如果是文件夹，递归调用，保持文件夹名称不变
                copy_files(src_path, dest_path)
            else:
                # 处理文件名冲突，直接使用数字命名
                file_counter = 1
                new_dest_path = os.path.join(dest_folder, str(file_counter))

                # 检查文件名冲突
                while os.path.exists(new_dest_path):
                    file_counter += 1
                    new_dest_path = os.path.join(dest_folder, str(file_counter))

                # 复制文件
                shutil.copy2(src_path, new_dest_path)



class Predictor(BasePredictor):
    def setup(self, weights: str):
        if bool(weights):
            self.handle_user_weights(weights)

        self.comfyUI = ComfyUI("127.0.0.1:8188")
        self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)

    def handle_user_weights(self, weights: str):
        print(f"Downloading user weights from: {weights}")
        WeightsDownloader.download("weights.tar", weights, config["USER_WEIGHTS_PATH"])
        for item in os.listdir(config["USER_WEIGHTS_PATH"]):
            source = os.path.join(config["USER_WEIGHTS_PATH"], item)
            destination = os.path.join(config["MODELS_PATH"], item)
            if os.path.isdir(source):
                if not os.path.exists(destination):
                    print(f"Moving {source} to {destination}")
                    shutil.move(source, destination)
                else:
                    for root, _, files in os.walk(source):
                        for file in files:
                            if not os.path.exists(os.path.join(destination, file)):
                                print(
                                    f"Moving {os.path.join(root, file)} to {destination}"
                                )
                                shutil.move(os.path.join(root, file), destination)
                            else:
                                print(
                                    f"Skipping {file} because it already exists in {destination}"
                                )

    def handle_input_file(self, input_file: Path, index):
        file_extension = os.path.splitext(input_file)[1].lower()
        if file_extension == ".tar":
            with tarfile.open(input_file, "r") as tar:
                tar.extractall(INPUT_DIR)
        elif file_extension == ".zip":
            with zipfile.ZipFile(input_file, "r") as zip_ref:
                zip_ref.extractall(INPUT_DIR)
        elif file_extension in [".jpg", ".jpeg", ".png", ".webp"]:
            shutil.copy(input_file, os.path.join(INPUT_DIR, f"input{index}{file_extension}"))
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")

        print("====================================")
        print(f"Inputs uploaded to {INPUT_DIR}:")
        self.comfyUI.get_files(INPUT_DIR)

        # 同步输入文件
        copy_files(INPUT_DIR, COMFYUI_INPUTS)
        print("====================================")

    def predict(
        self,
        workflow_json: str = Input(
            description="请输入ComfyUI工作流的API JSON版本。（进入ComfyUI设置并打开“启用开发模式选项”，然后通过“保存(API格式)”按钮保存ComfyUI工作流）",
            default="",
        ),
        input_file1: Path = Input(
            description="输入图片。",
            default=None,
        ),
        input_file2: Path = Input(
            description="输入图片。",
            default=None,
        ),
        return_temp_files: bool = Input(
            description="返回任意过程中产生的图片，用于排除错误。",
            default=False,
        ),
        output_format: str = optimise_images.predict_output_format(),
        output_quality: int = optimise_images.predict_output_quality(),
        randomise_seeds: bool = Input(
            description="自动随机化种子(seed, noise_seed, rand_seed)",
            default=True,
        ),
        force_reset_cache: bool = Input(
            description="在运行工作流之前强制重置ComfyUI缓存，用于调试。",
            default=False,
        ),
    ) -> List[Path]:
        """Run a single prediction on the model"""
        self.comfyUI.cleanup(ALL_DIRECTORIES)


        if input_file1:
            self.handle_input_file(input_file1, 1)
        if input_file2:
            self.handle_input_file(input_file2, 2)

        wf = self.comfyUI.load_workflow(workflow_json or EXAMPLE_WORKFLOW_JSON)

        self.comfyUI.connect()

        if force_reset_cache or not randomise_seeds:
            self.comfyUI.reset_execution_cache()

        if randomise_seeds:
            self.comfyUI.randomise_seeds(wf)

        self.comfyUI.run_workflow(wf)

        output_directories = [OUTPUT_DIR]

        # 同步输出文件
        copy_files(OUTPUT_DIR, COMFYUI_OUTPUTS)
        if return_temp_files:
            output_directories.append(COMFYUI_TEMP_OUTPUT_DIR)

        return optimise_images.optimise_image_files(
            output_format, output_quality, self.comfyUI.get_files(output_directories)
        )

