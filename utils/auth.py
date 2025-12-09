
# State in memory to track authentication
# Structure: { user_id: {'attempts': 0, 'authenticated': False} }
_auth_state = {}

PASSWORD = "ValorP"
MAX_ATTEMPTS = 10

def is_authenticated(user_id: int) -> bool:
    """Checks if a user is authenticated."""
    state = _auth_state.get(user_id)
    return state is not None and state.get('authenticated', False)

def get_attempts(user_id: int) -> int:
    """Gets the number of failed attempts for a user."""
    state = _auth_state.get(user_id, {})
    return state.get('attempts', 0)

def register_attempt(user_id: int, text: str) -> bool:
    """
    Registers an authentication attempt.
    Returns True if authentication was successful (password matches).
    Returns False otherwise (increments attempt counter).
    """
    if user_id not in _auth_state:
        _auth_state[user_id] = {'attempts': 0, 'authenticated': False}
    
    state = _auth_state[user_id]
    
    # If already authenticated, nothing to do (shouldn't be reached ideally)
    if state['authenticated']:
        return True

    if text and text.strip() == PASSWORD:
        state['authenticated'] = True
        return True
    
    state['attempts'] += 1
    return False

def is_blocked(user_id: int) -> bool:
    """Checks if the user has exceeded the max attempts."""
    return get_attempts(user_id) >= MAX_ATTEMPTS
