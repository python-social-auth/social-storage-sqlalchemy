from social.utils import set_current_strategy_getter
from social_flask.utils import load_strategy


set_current_strategy_getter(load_strategy)
