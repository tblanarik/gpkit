# -*- coding: utf-8 -*-
"Module containing the substitution function"

import numpy as np

from collections import defaultdict
from collections import Iterable

from .small_classes import Numbers, Strings
from .small_classes import HashVector
from .nomials import Monomial
from .nomials import VarKey
from .nomials import VectorVariable

from .small_scripts import locate_vars
from .small_scripts import is_sweepvar
from .small_scripts import mag

from . import units as ureg
from . import DimensionalityError
Quantity = ureg.Quantity
Numbers += (Quantity,)


def vectorsub(subs, var, sub, varset):
    "Vectorized substitution via vecmons and Variables."
    try:
        isvector = "length" in var.descr and "idx" not in var.descr
        var = VectorVariable(**var.descr)
    except:
        try:
            assert len(var)
            isvector = True
        except:
            isvector = False

    if isvector:
        if isinstance(sub, VarKey):
            sub = VectorVariable(**sub.descr)
        if len(var) == len(sub):
            for i in range(len(var)):
                v = VarKey(var[i])
                if v in varset:
                    subs[v] = sub[i]
        else:
            raise ValueError("tried substituting %s for %s, but their"
                             " lengths were unequal." % (sub, var))
    elif var in varset:
        subs[var] = sub


def substitution(varlocs, varkeys, exps, cs, substitutions, val=None):
    """Efficient substituton into a list of monomials.

        Parameters
        ----------
        varlocs : dict
            Dictionary of monomial indexes for each variable.
        exps : dict
            Dictionary of variable exponents for each monomial.
        cs : list
            Coefficients each monomial.
        substitutions : dict
            Substitutions to apply to the above.
        val : number (optional)
            Used to substitute singlet variables.

        Returns
        -------
        varlocs_ : dict
            Dictionary of monomial indexes for each variable.
        exps_ : dict
            Dictionary of variable exponents for each monomial.
        cs_ : list
            Coefficients each monomial.
        subs_ : dict
            Substitutions to apply to the above.
    """

    if val is not None:
        substitutions = {substitutions: val}

    subs = {}
    varset = frozenset(varlocs.keys())
    for var, sub in substitutions.items():
        if not is_sweepvar(sub):
            if isinstance(var, Monomial):
                var_ = VarKey(var)
                if var_ in varset:
                    subs[var_] = sub
            elif isinstance(var, Strings):
                    if var in varkeys:
                        var_ = varkeys[var]
                        vectorsub(subs, var_, sub, varset)
            else:
                vectorsub(subs, var, sub, varset)

    if not subs:
        raise KeyError("could not find anything to substitute in %s" % substitutions)

    exps_ = [HashVector(exp) for exp in exps]
    cs_ = np.array(cs)
    varlocs_ = defaultdict(list)
    varlocs_.update({var: list(idxs) for (var, idxs) in varlocs.items()})
    for var, sub in subs.items():
        for i in varlocs[var]:
            x = exps_[i].pop(var)
            varlocs_[var].remove(i)
            if len(varlocs_[var]) == 0:
                del varlocs_[var]
            if isinstance(sub, Numbers):
                cs_[i] *= sub**x
            elif isinstance(sub, np.ndarray):
                if not sub.shape:
                    cs_[i] *= sub.flatten()[0]**x
            elif isinstance(sub, Strings):
                descr = dict(var.descr)
                del descr["name"]
                sub = VarKey(name=sub, **descr)
                exps_[i] += HashVector({sub: x})
                varlocs_[sub].append(i)
            elif isinstance(sub, VarKey):
                sub = VarKey(sub)
                if isinstance(var.descr["units"], Quantity):
                    try:
                        cs_[i] *= (var.descr["units"]/sub.descr["units"]).to('dimensionless')
                    except DimensionalityError:
                        raise ValueError("substituted variables must have the same units"
                                         " as the variables they replace.")
                exps_[i] += HashVector({sub: x})
                varlocs_[sub].append(i)
            elif isinstance(sub, Monomial):
                if isinstance(var.descr["units"], Quantity):
                    try:
                        cs_[i] *= (var.descr["units"]/sub.units).to('dimensionless')
                    except DimensionalityError:
                        raise ValueError("substituted monomials must have the same units"
                                         " as the variables they replace.")
                exps_[i] += x*sub.exp
                cs_[i] *= mag(sub.c)**x
                for subvar in sub.exp:
                    varlocs_[subvar].append(i)
            else:
                raise TypeError("could not substitue with value of type '%s'" % type(sub))
    return varlocs_, exps_, cs_, subs
