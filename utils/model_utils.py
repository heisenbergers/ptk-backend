from transformers import AutoProcessor
from vllm import LLM, SamplingParams
from qwen_vl_utils import process_vision_info # Assuming this is a local utility or correctly installed
from config import PTKConfig
import torch
import os # Import the os module

class ModelOperations:

    @classmethod
    def load_model_and_processor(self, checkpoint=PTKConfig.model_checkpoint, min_pixels=PTKConfig.min_pixels, max_pixels=PTKConfig.max_pixels):
        """Initialises the VLLM engine, processor, and sampling parameters.
        Reads max_model_len and gpu_memory_utilization from environment variables
        VLLM_MAX_MODEL_LEN and VLLM_GPU_MEMORY_UTILIZATION respectively,
        with fallbacks to 50000 and 0.95.

        Args:
            checkpoint (str): File path of model folder (HF Format)
            min_pixels (int): minimum pixels
            max_pixels (int): maximum pixels

        Returns:
            llm (LLM): VLLM engine instance
            processor (AutoProcessor): Processor class for tokenisation and chat template application
            sampling_params (SamplingParams): Sampling parameters for VLLM
        """
        try:
            max_model_len_env = os.getenv("max_model_len")
            max_model_len = int(max_model_len_env) if max_model_len_env is not None else 25000
            if max_model_len <= 0: 
                print(f"Warning: Invalid max_model_len value '{max_model_len_env}'. Falling back to 25000.")
                max_model_len = 25000
        except ValueError:
            print(f"Warning: Could not parse max_model_len environment variable ('{max_model_len_env}'). Falling back to 25000.")
            max_model_len = 25000
        except Exception as e:
            print(f"Warning: Error reading max_model_len: {e}. Falling back to 25000.")
            max_model_len = 25000


        try:
            gpu_memory_utilization_env = os.getenv("gpu_memory_utilization")
            gpu_memory_utilization = float(gpu_memory_utilization_env) if gpu_memory_utilization_env is not None else 0.95
            if not (0 < gpu_memory_utilization <= 1): 
                print(f"Warning: Invalid gpu_memory_utilization value '{gpu_memory_utilization_env}'. Falling back to 0.0.95.")
                gpu_memory_utilization = 0.95
        except ValueError:
            print(f"Warning: Could not parse gpu_memory_utilization environment variable ('{gpu_memory_utilization_env}'). Falling back to 0.95.")
            gpu_memory_utilization = 0.95
        except Exception as e:
            print(f"Warning: Error reading gpu_memory_utilization: {e}. Falling back to 0.95.")
            gpu_memory_utilization = 0.95

        print(f"Initializing LLM with max_model_len: {max_model_len}, gpu_memory_utilization: {gpu_memory_utilization}")

        try:
            limit_mm_image_env = os.getenv("mm_image")
            limit_mm_image = int(limit_mm_image_env) if limit_mm_image_env is not None else 10
            if limit_mm_image < 0: # Basic validation (allow 0 if that's a valid VLLM setting)
                print(f"Warning: Invalid mm_image value '{limit_mm_image_env}'. Falling back to 10.")
                limit_mm_image = 10
        except ValueError:
            print(f"Warning: Could not parse mm_image environment variable ('{limit_mm_image_env}'). Falling back to 10.")
            limit_mm_image = 10
        except Exception as e:
            print(f"Warning: Error reading mm_image: {e}. Falling back to 10.")
            limit_mm_image = 10

        try:
            limit_mm_video_env = os.getenv("mm_video")
            limit_mm_video = int(limit_mm_video_env) if limit_mm_video_env is not None else 20
            if limit_mm_video < 20: 
                print(f"Warning: Invalid mm_video value '{limit_mm_video_env}'. Falling back to 10.")
                limit_mm_video = 20
        except ValueError:
            print(f"Warning: Could not parse mm_video environment variable ('{limit_mm_video_env}'). Falling back to 10.")
            limit_mm_video = 20
        except Exception as e:
            print(f"Warning: Error reading mm_video: {e}. Falling back to 10.")
            limit_mm_video = 20

        limit_mm_per_prompt_dict = {"image": limit_mm_image, "video": limit_mm_video}

        llm = LLM(
            model=checkpoint,
            trust_remote_code=True,
            limit_mm_per_prompt=limit_mm_per_prompt_dict,
            quantization='awq_marlin',
            dtype=torch.bfloat16,
            max_model_len=max_model_len,
            enforce_eager=True,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        
        processor = AutoProcessor.from_pretrained(
            checkpoint,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
            use_fast=True # As per original code
        )

        # Initialize SamplingParams
        sampling_params = SamplingParams(
            temperature=PTKConfig.temperature if hasattr(PTKConfig, 'temperature') else 0.1,
            top_p=PTKConfig.top_p if hasattr(PTKConfig, 'top_p') else 0.001, # Corrected typo from 'temperature' to 'top_p'
            repetition_penalty=1.05, # As per original code
            max_tokens=PTKConfig.max_new_tokens if hasattr(PTKConfig, 'max_new_tokens') else 40960,
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
                    # Assuming file_path is a path to a video file
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

        # Process vision information
        # Ensure qwen_vl_utils.process_vision_info is compatible with your setup
        # The original code had a placeholder comment for qwen_vl_utils
        try:
            image_inputs, video_inputs, video_kwargs = process_vision_info(messages, return_video_kwargs=True)
        except Exception as e:
            print(f"Error in process_vision_info: {e}")
            # Handle the error appropriately, perhaps by raising it or setting vision inputs to None
            image_inputs, video_inputs, video_kwargs = None, None, {}


        mm_data = {}
        if image_inputs is not None:
            mm_data["image"] = image_inputs
        if video_inputs is not None:
            mm_data["video"] = video_inputs
        
        llm_inputs = {
            "prompt": prompt_text,
            "multi_modal_data": mm_data if mm_data else None, # Pass None if mm_data is empty
            "mm_processor_kwargs": video_kwargs if video_kwargs else None, # Pass None if video_kwargs is empty
        }

        try:
            # Inference stage using VLLM
            outputs = llm.generate([llm_inputs], sampling_params=sampling_params)
            generated_text = outputs[0].outputs[0].text
            return generated_text
        
        except Exception as e:
            print(f"VLLM Inference Exception: {e}")
            # It's good practice to re-raise the exception or handle it more specifically
            raise e
