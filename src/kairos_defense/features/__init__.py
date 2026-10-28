"""Features and signatures (SPEC §9): resampling, target frames, channels, signatures, PAA windows.

Algorithms here are pure functions over numpy and pandas. ``build.py`` runs them over every track
for ``kairos-defense index`` and writes the results through the store adapters.
"""
