from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
import torch
from qwen_vl_utils import process_vision_info
from config import settings, ResponseModel
from transformers import BitsAndBytesConfig

class ModelOperations:

    @classmethod
    def load_model_and_processor(self, checkpoint=settings.model_checkpoint, min_pixels = settings.min_pixels, max_pixels = settings.max_pixels):
        """Initialises and loads the Qwen2.5-VL model and its processor.

        Configuration for quantization (4-bit, 8-bit, or none) is taken from settings.

        Args:
            checkpoint (str, optional): The Hugging Face model checkpoint name or path.
                                        Defaults to settings.model_checkpoint.
            min_pixels (int, optional): Minimum number of pixels for image/video processing.
                                        Defaults to settings.min_pixels.
            max_pixels (int, optional): Maximum number of pixels for image/video processing.
                                        Defaults to settings.max_pixels.

        Returns:
            tuple: A tuple containing:
                - model (Qwen2_5_VLForConditionalGeneration): The loaded model.
                - processor (AutoProcessor): The loaded processor.
        """
        if settings.quantization == "4bit":
            quantization_config = BitsAndBytesConfig(load_in_4bit=True)
        elif settings.quantization == "8bit":
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        elif settings.quantization == "16bit":
            quantization_config = None

        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            checkpoint,
            torch_dtype="auto",
            device_map="auto",
            attn_implementation="flash_attention_2",
            quantization_config=quantization_config
    )

        processor = AutoProcessor.from_pretrained(
        checkpoint,
        min_pixels=min_pixels,
        max_pixels=max_pixels,
        use_fast=True
    )

        return model, processor

    @staticmethod
    def inference(model,
                  processor,
                  system_prompt,
                  user_prompt,
                  file_path,
                  max_new_tokens=3000):
        """Performs inference using the loaded Qwen2.5-VL model and processor.

        It constructs a message list with system and user prompts (including video/image),
        processes the inputs, generates text, and decodes the output.

        Args:
            model (Qwen2_5_VLForConditionalGeneration): The loaded Qwen2.5-VL model.
            processor (AutoProcessor): The loaded processor for the model.
            system_prompt (str): The system prompt to guide the model's behavior.
            user_prompt (str): The user's textual prompt.
            file_path (str): The path to the video or image file to be analyzed.
            max_new_tokens (int, optional): The maximum number of new tokens to generate.
                                            Defaults to 3000.

        Raises:
            Exception: Any exception that occurs during the inference process.
                       Clears CUDA cache if an exception occurs.

        Returns:
            str: The generated text output from the model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "video", "video": file_path}, {"type": "text", "text": user_prompt}]},
        ]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        try:
        # inference stage
            with torch.inference_mode():
                generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
            generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
            output_texts = processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )
            return output_texts[0]

        except Exception as e:
            torch.cuda.empty_cache()
            raise e