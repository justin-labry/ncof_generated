from gymnasium.envs.registration import register

from .env import ACTION_NAMES, ACTIVE, DEEP_SLEEP, NcofGnb2Env

register(id="NcofGnb2-v0", entry_point="gym_for_ncof.env:NcofGnb2Env")

__all__ = ["NcofGnb2Env", "ACTION_NAMES", "ACTIVE", "DEEP_SLEEP"]
