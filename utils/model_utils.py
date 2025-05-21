from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
import torch
from qwen_vl_utils import process_vision_info
from config import PTKConfig, ResponseModel
from transformers import BitsAndBytesConfig\

class ModelOperations:
    checkpoint = PTKConfig.model_checkpoint
    min_pixels = 256*28*28
    max_pixels = 1280*28*28

    @classmethod
    def load_model_and_processor(self, checkpoint=checkpoint, min_pixels = min_pixels, max_pixels = max_pixels):
        """Initialises the model and processor

        Args:
            checkpoint (str): File path of model folder (HF Format)
            min_pixels (int): minimum pixels
            max_pixels (int): maximum pixels

        Returns:
            model (Qwen2_5_VLForConditionalGeneration): Model class for generation
            processor (AutoProcessor): Processor class for tokenisation and chat template application

        """
        if PTKConfig.quantization == "4bit":
            quantization_config = BitsAndBytesConfig(load_in_4bit=True)
        elif PTKConfig.quantization == "8bit":
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        elif PTKConfig.quantization == "16bit":
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


        