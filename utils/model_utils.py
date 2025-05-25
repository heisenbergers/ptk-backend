from transformers import AutoProcessor
from vllm import LLM, SamplingParams
from qwen_vl_utils import process_vision_info
from config import PTKConfig
import torch

class ModelOperations:

    @classmethod
    def load_model_and_processor(self, checkpoint=PTKConfig.model_checkpoint, min_pixels=PTKConfig.min_pixels, max_pixels=PTKConfig.max_pixels):
        """Initialises the VLLM engine, processor, and sampling parameters.

        Args:
            checkpoint (str): File path of model folder (HF Format)
            min_pixels (int): minimum pixels
            max_pixels (int): maximum pixels

        Returns:
            llm (LLM): VLLM engine instance
            processor (AutoProcessor): Processor class for tokenisation and chat template application
            sampling_params (SamplingParams): Sampling parameters for VLLM
        """
        llm = LLM(
            model=checkpoint,
            trust_remote_code=True,
            limit_mm_per_prompt={"image": 10, "video": 10},
            quantization='awq_marlin',
            dtype=torch.bfloat16,
            max_model_len=40960,
            enforce_eager=True,
            gpu_memory_utilization=0.95,
        )
        
        processor = AutoProcessor.from_pretrained(
            checkpoint,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
            use_fast=True
        )

        # Initialize SamplingParams (from the example script)
        # You can expose these parameters or configure them via PTKConfig if needed
        sampling_params = SamplingParams(
            temperature=PTKConfig.temperature if hasattr(PTKConfig, 'temperature') else 0.1,
            top_p=PTKConfig.top_p if hasattr(PTKConfig, 'temperature') else 0.001,
            repetition_penalty=1.05,
            max_tokens=PTKConfig.max_new_tokens if hasattr(PTKConfig, 'max_new_tokens') else 40960, # Use from PTKConfig or default
            stop_token_ids=[], 
        )

        return llm, processor, sampling_params
    
    @staticmethod
    def inference(llm, 
                  processor,
                  sampling_params, 
                  system_prompt,
                  user_prompt,
                  file_path, 
                  ):
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": [
                    {"type": "video", "video": file_path},
                    {"type": "text", "text": user_prompt}
                ]
            },
        ]
        
        # Apply chat template
        prompt_text = processor.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )


        image_inputs, video_inputs, video_kwargs = process_vision_info(messages, return_video_kwargs=True)

        mm_data = {}
        if image_inputs is not None:
            mm_data["image"] = image_inputs
        if video_inputs is not None:
            mm_data["video"] = video_inputs
        
        llm_inputs = {
            "prompt": prompt_text,
            "multi_modal_data": mm_data,
            "mm_processor_kwargs": video_kwargs, 
        }

        try:
            # Inference stage using VLLM
            outputs = llm.generate([llm_inputs], sampling_params=sampling_params)
            generated_text = outputs[0].outputs[0].text
            return generated_text
        
        except Exception as e:
            print(f"VLLM Inference Exception: {e}")
            raise e
        