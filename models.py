
MODELS = {

    "groq": [
        {
            "id": "openai/gpt-oss-120b",
            "name": "GPT-OSS 120B",
            "type": "open-weight",
            "cost_tier": "free",
            "capabilities": ["reasoning", "coding", "general"],
            "supports_tools": True,
            "native_web_search": True,
            "web_search_cost": "unknown",
            "context_window": None,
            "enabled": True
        },
        {
            "id": "openai/gpt-oss-20b",
            "name": "GPT-OSS 20B",
            "type": "open-weight",
            "cost_tier": "free",
            "capabilities": ["reasoning", "coding", "general"],
            "supports_tools": True,
            "native_web_search": False,
            "web_search_cost": "unknown",
            "context_window": 131072,
            "enabled": True
        }
    ],

    "openai": [],

    "gemini": [
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "type": "stable",
            "cost_tier": "free",
            "capabilities": ["general", "reasoning", "coding", "vision"],
            "supports_tools": True,
            "native_web_search": False,
            "web_search_cost": "unknown",
            "context_window": 1048576,
            "enabled": False
        },
        {
            "id": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite",
            "type": "stable",
            "cost_tier": "free",
            "capabilities": ["general", "coding"],
            "supports_tools": True,
            "native_web_search": False,
            "web_search_cost": "unknown",
            "context_window": 1048576,
            "enabled": False
        },
        {
            "id": "gemini-3.5-flash",
            "name": "Gemini 3.5 Flash",
            "type": "stable",
            "cost_tier": "free",
            "capabilities": ["general", "reasoning", "coding"],
            "supports_tools": True,
            "native_web_search": False,
            "web_search_cost": "unknown",
            "context_window": None,
            "enabled": True
        },
        {
            "id": "gemini-3.8-flash",
            "name": "Gemini 3.8 Flash",
            "type": "stable",
            "cost_tier": "free",
            "capabilities": ["general", "reasoning"],
            "supports_tools": True,
            "native_web_search": False,
            "web_search_cost": "unknown",
            "context_window": None,
            "enabled": False
        }
    ],

    "mistral": [],

    "openrouter": [
        {
            "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "name": "NVIDIA Nemotron 3 Ultra 550B",
            "type": "free",
            "cost_tier": "free",
            "capabilities": ["reasoning", "coding", "general"],
            "supports_tools": False,
            "native_web_search": False,
            "web_search_cost": "not_available",
            "context_window": None,
            "enabled": True
        },
        {
            "id": "nvidia/nemotron-3.5-super-vl:free",
            "name": "NVIDIA Nemotron 3.5 Super VL",
            "type": "free",
            "cost_tier": "free",
            "capabilities": ["reasoning", "vision", "general"],
            "supports_tools": False,
            "native_web_search": False,
            "web_search_cost": "not_available",
            "context_window": None,
            "enabled": True
        },
        {
            "id": "google/gemma-4-26b-a4b-it:free",
            "name": "Google Gemma 4",
            "type": "free",
            "cost_tier": "free",
            "capabilities": ["general", "coding"],
            "supports_tools": False,
            "native_web_search": False,
            "web_search_cost": "not_available",
            "context_window": None,
            "enabled": True
        },
	{
    	    "id": "nvidia/nemotron-3.5-lightning:free",
    	    "name": "NVIDIA Nemotron 3.5 Lightning",
    	    "type": "free",
   	    "cost_tier": "free",
    	    "capabilities": ["reasoning", "coding", "general"],
    	    "supports_tools": True,
    	    "native_web_search": False,
    	    "web_search_cost": "not_available",
    	    "context_window": 1048576,
    	    "enabled": True
	},
	{
    	    "id": "cohere/north-mini-code:free",
    	    "name": "Cohere North Mini Code",
    	    "type": "free",
    	    "cost_tier": "free",
    	    "capabilities": ["coding", "reasoning", "general"],
    	    "supports_tools": True,
    	    "native_web_search": False,
    	    "web_search_cost": "not_available",
    	    "context_window": 262144,
    	    "enabled": True
	},
	{
    	    "id": "dots-studio/dots-3-note-preview:free",
    	    "name": "Dots3 Note Preview",
    	    "type": "free",
    	    "cost_tier": "free",
    	    "capabilities": ["reasoning", "coding", "general", "vision"],
    	    "supports_tools": True,
    	    "native_web_search": False,
    	    "web_search_cost": "not_available",
    	    "context_window": 512000,
    	    "enabled": True
	},
	{
    	    "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    	    "name": "NVIDIA Nemotron 3 Nano Omni Reasoning",
    	    "type": "free",
    	    "cost_tier": "free",
    	    "capabilities": ["reasoning", "general"],
    	    "supports_tools": False,
    	    "native_web_search": False,
    	    "web_search_cost": "not_available",
    	    "context_window": 262144,
    	    "enabled": True
	},
	{
    	    "id": "recursive/flint-v1.0:free",
    	    "name": "Recursive Flint V1.0",
    	    "type": "free",
    	    "cost_tier": "free",
    	    "capabilities": ["coding", "reasoning", "general"],
    	    "supports_tools": False,
    	    "native_web_search": False,
    	    "web_search_cost": "not_available",
    	    "context_window": 262144,
    	    "enabled": True
	}
    ]

}


def get_available_models(provider=None):

    if provider:
        return [
            model for model in MODELS.get(provider, [])
            if model.get("enabled", True)
        ]

    return {
        provider: [
            model for model in models
            if model.get("enabled", True)
        ]
        for provider, models in MODELS.items()
    }

