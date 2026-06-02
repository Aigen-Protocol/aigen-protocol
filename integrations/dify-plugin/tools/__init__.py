"""OABP / AIGEN Dify tools package.

Holds the five tool implementations (``list_missions``, ``get_mission``,
``create_mission``, ``submit_mission``, ``get_stats``), their shared HTTP client
(``oabp_api``) and the tool base mixin (``_base``). Each tool is declared by a
sibling ``<name>.yaml`` and discovered by Dify via the provider manifest.
"""
