import random

class SmartAI:
    def __init__(self):
        self.model_name = "PPO-Home-Optimizer"

    def generate_recommendation(self, preferences, environment, history):
        """
        In a real PPO model, this would use a neural network.
        For now, this is just a logic that simulates the AI's decision.
        """
        
        # Example Logic: Energy Saving Recommendation
        current_temp = environment.get("outdoor_temp", 25)
        user_pref_temp = preferences[0].value if preferences else 22
        
        # Simulating a "Smart" decision
        if current_temp > 30 and user_pref_temp < 20:
            recommendation = "Set AC to 24°C"
            reason = "It's very hot outside. Increasing AC by 4°C will save 15% energy without losing much comfort."
            action_value = 24
            confidence = 0.85
        else:
            recommendation = "Maintain current settings"
            reason = "Current settings are optimal for energy efficiency."
            action_value = user_pref_temp
            confidence = 0.95

        return {
            "recommendation": recommendation,
            "action": action_value,
            "confidence": confidence,
            "reason": reason
        }

# We create one instance of the AI to be used by the backend
recommender = SmartAI()