from persistent_memory.persistent_memory_record import classify_memory_consent


class PendingActionRouter:
    def handle(self, pending_action, user_input: str):
        decision = classify_memory_consent(user_input)

        if pending_action.action_type == "SAVE_MEMORY":
            if decision in {"APPROVED", "REJECTED"}:
                return {
                    "complete": True,
                    "action": "SAVE_MEMORY",
                    "storage_scope": "PERSISTENT",
                    "memory_text": pending_action.payload["memory_text"],
                    "operator_confirmation": user_input,
                    "authorization_state": decision,
                }

            if decision == "SESSION_ONLY":
                return {
                    "complete": True,
                    "action": "SAVE_MEMORY",
                    "storage_scope": "SESSION_ONLY",
                    "memory_text": pending_action.payload["memory_text"],
                    "operator_confirmation": user_input,
                    "authorization_state": "NOT_REQUIRED",
                }

            return {
                "complete": False,
                "message": "No save performed. Please choose yes (persistent), no, or session-only."
            }

        return {
            "complete": False,
            "message": "Unknown pending action."
        }
