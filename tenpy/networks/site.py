"""Defines a class describing the local physical Hilbert space.

The :class:`Site` is the prototype, read it's docstring.
We
"""
# Copyright 2018 TeNPy Developers

import copy
import numpy as np

from ..linalg import np_conserved as npc
from ..tools.misc import inverse_permutation

__all__ = [
    'Site', 'DoubleSite', 'SpinHalfSite', 'SpinSite', 'FermionSite', 'SpinHalfFermionSite',
    'BosonSite'
]


class Site(object):
    """Collects necessary information about a single local site of a lattice.

    This class defines what the local basis states are: it provides the :attr:`leg`
    defining the charges of the physical leg for this site.
    Moreover, it stores (local) on-site operators, which are directly available as attribute,
    e.g., ``self.Sz`` is the Sz operator for the :class:`SpinSite`.
    Alternatively, operators can be obained with :meth:`get_op`.
    The operator names ``Id`` and ``JW`` are reserved for the identy and Jordan-Wigner strings.

    .. warning ::
        The order of the local basis can change depending on the charge conservation!
        This is a *necessary* feature since we need to sort the basis by charges for efficiency.
        We use the :attr:`state_labels` (and :attr:`perm`) to keep track of these permutations.

    Parameters
    ----------
    leg : :class:`~tenpy.linalg.charges.LegCharge`
        Charges of the physical states, to be used for the physical leg of MPS & co).
    state_labels : None | list of str
        Optionally a label for each local basis states. ``None`` entries are ignored / not set.
    **site_ops :
        Additional keyword arguments of the form ``name=op`` given to :meth:`add_op`.
        The identity operator ``'Id'`` is automatically included.
        If no ``'JW'`` for the Jordan-Wigner string is given,
        ``'JW'`` is set as an alias to ``'Id'``.

    Attributes
    ----------
    dim
    onsite_ops
    leg : :class:`~tenpy.linalg.charges.LegCharge`
        Charges of the local basis states.
    state_labels : {str: int}
        (Optional) labels for the local basis states.
    opnames : set
        Labels of all onsite operators (i.e. ``self.op`` exists if ``'op'`` in ``self.opnames``).
        Note that :meth:`get_op` allow arbitrary concatenations of them.
    need_JW_string : set
        Labels of all onsite operators that need a Jordan-Wigner string.
    ops : :class:`~tenpy.linalg.np_conserved.Array`
        Onsite operators are added directly as attributes to self.
        For example after ``self.add_op('Sz', Sz)`` you can use ``self.Sz`` for the `Sz` operator.
        All onsite operators have labels ``'p', 'p*'``.
    perm : 1D array
        Index permutation of the physical leg compared to `conserve=None`.
    JW_exponent : 1D array
        Exponents of the ``'JW'`` operator, such that
        ``self.JW.to_ndarray() = np.diag(np.exp(1.j*np.pi* JW_exponent))``

    Examples
    --------
    The following generates a site for spin-1/2 with Sz conservation.
    Note that ``Sx = (Sp + Sm)/2`` violates Sz conservation and is thus not a valid
    on-site operator.

    >>> chinfo = npc.ChargeInfo([1], ['Sz'])
    >>> ch = npc.LegCharge.from_qflat(chinfo, [1, -1])
    >>> Sp = [[0, 1.], [0, 0]]
    >>> Sm = [[0, 0], [1., 0]]
    >>> Sz = [[0.5, 0], [0, -0.5]]
    >>> site = Site(ch, ['up', 'down'], Splus=Sp, Sminus=Sm, Sz=Sz)
    >>> print site.Splus.to_ndarray()
    array([[ 0.,  1.],
           [ 0.,  0.]])
    >>> print site.get_op('Sminus').to_ndarray()
    array([[ 0.,  0.],
           [ 1.,  0.]])
    >>> print site.get_op('Splus Sminus').to_ndarry()
    array([[ 1.,  0.],
           [ 0.,  0.]])
    """

    def __init__(self, leg, state_labels=None, **site_ops):
        self.leg = leg
        self.state_labels = dict()
        if state_labels is not None:
            for i, v in enumerate(state_labels):
                if v is not None:
                    self.state_labels[str(v)] = i
        self.opnames = set()
        self.need_JW_string = set()
        self.add_op('Id', npc.diag(1., self.leg))
        for name, op in site_ops.items():
            self.add_op(name, op)
        if not hasattr(self, 'perm'):  # default permutation for the local states
            self.perm = np.arange(self.dim)
        if 'JW' not in self.opnames:
            # include trivial `JW` to allow combinations
            # of bosonic and fermionic sites in an MPS
            self.add_op('JW', self.Id)
        self.test_sanity()

    def copy_change_charge(self, new_leg_charge=None, permute=None):
        """Generate a copy of a site with different charges.

        Parameters
        ----------
        new_leg_charge : :class:`LegCharge` | None
            The new charges to be used. If ``None``, use trivial charges.
        permute : ``None`` | ndarray
            Ignored if ``None``; otherwise an permuation applied to the physical leg.

        Returns
        -------
        cpy : :class:`Site`
            A copy of `self` with a different (possibly permuted) :attr:`leg`.
        """
        if new_leg_charge is None:
            new_leg_charge = npc.LegCharge.from_trivial(self.dim)
        cpy = copy.deepcopy(self)
        cpy.leg = new_leg_charge
        if permute is not None:
            permute = np.asarray(permute, dtype=np.intp)
            inv_perm = inverse_permutation(permute)
            cpy.perm = self.perm[permute]
        for opname in self.opnames:
            cpy.remove_op(opname)
            op = self.get_op(opname).to_ndarray()
            if permute is not None:
                op = op[np.ix_(permute, permute)]
            cpy.add_op(opname, op, opname in self.need_JW_string)
        if permute is not None:
            for label in self.state_labels:
                cpy.state_labels[label] = inv_perm[self.state_labels[label]]
        return cpy

    def test_sanity(self):
        """Sanity check. Raises ValueErrors, if something is wrong."""
        for lab, ind in self.state_labels.items():
            if not isinstance(lab, str):
                raise ValueError("wrong type of state label")
            if not 0 <= ind < self.dim:
                raise ValueError("index of state label out of bounds")
        for name in self.opnames:
            if not hasattr(self, name):
                raise ValueError("missing onsite operator " + name)
        for op in self.onsite_ops.values():
            if op.rank != 2:
                raise ValueError("only rank-2 onsite operators allowed")
            op.legs[0].test_equal(self.leg)
            op.legs[1].test_contractible(self.leg)
            op.test_sanity()
        for op in self.need_JW_string:
            assert op in self.opnames
        np.testing.assert_array_almost_equal(
            np.diag(np.exp(1.j * np.pi * self.JW_exponent)), self.JW.to_ndarray(), 15)

    @property
    def dim(self):
        """Dimension of the local Hilbert space"""
        return self.leg.ind_len

    @property
    def onsite_ops(self):
        """Dictionary of on-site operators for iteration.

        (single operators are accessible as attributes.)"""
        return dict([(name, getattr(self, name)) for name in sorted(self.opnames)])

    def add_op(self, name, op, need_JW=False):
        """Add one on-site operators

        Parameters
        ----------
        name : str
            A valid python variable name, used to label the operator.
            The name under which `op` is added as attribute to self.
        op : np.ndarray | :class:`~tenpy.linalg.np_conserved.Array`
            A matrix acting on the local hilbert space representing the local operator.
            Dense numpy arrays are automatically converted to
            :class:`~tenpy.linalg.np_conserved.Array`.
            LegCharges have to be ``[leg, leg.conj()]``.
            We set labels ``'p', 'p*'``.
        need_JW : bool
            Wheter the operator needs a Jordan-Wigner string.
            If ``True``, the function adds `name` to :attr:`need_JW_string`.
        """
        name = str(name)
        if name in self.opnames:
            raise ValueError("operator with that name already existent: " + name)
        if hasattr(self, name):
            raise ValueError("Site already has that attribute name: " + name)
        if not isinstance(op, npc.Array):
            op = np.asarray(op)
            if op.shape != (self.dim, self.dim):
                raise ValueError("wrong shape of on-site operator")
            # try to convert op into npc.Array
            op = npc.Array.from_ndarray(op, [self.leg, self.leg.conj()])
        if op.rank != 2:
            raise ValueError("only rank-2 on-site operators allowed")
        op.legs[0].test_equal(self.leg)
        op.legs[1].test_contractible(self.leg)
        op.test_sanity()
        op.iset_leg_labels(['p', 'p*'])
        setattr(self, name, op)
        self.opnames.add(name)
        if need_JW:
            self.need_JW_string.add(name)
        if name == 'JW':
            self.JW_exponent = np.real_if_close(np.angle(np.diag(op.to_ndarray())) / np.pi)

    def rename_op(self, old_name, new_name):
        """Rename an added operator.

        Parameters
        ----------
        old_name : str
            The old name of the operator.
        new_name : str
            The new name of the operator.
        """
        if old_name == new_name:
            return
        if new_name in self.opnames:
            raise ValueError("new_name already exists")
        op = getattr(self, old_name)
        need_JW = old_name in self.need_JW_string
        self.remove_op(old_name)
        setattr(self, new_name, op)
        self.opnames.add(new_name)
        if need_JW:
            self.need_JW_string.add(new_name)
        if new_name == 'JW':
            self.JW_exponent = np.real_if_close(np.angle(np.diag(op.to_ndarray())) / np.pi)

    def remove_op(self, name):
        """Remove an added operator.

        Parameters
        ----------
        name : str
            The name of the operator to be removed.
        """
        self.opnames.remove(name)
        delattr(self, name)
        self.need_JW_string.discard(name)

    def state_index(self, label):
        """Return index of a basis state from its label.

        Parameters
        ----------
        label : int | string
            eather the index directly or a label (string) set before.

        Returns
        -------
        state_index : int
            the index of the basis state associated with the label.
        """
        res = self.state_labels.get(label, label)
        try:
            res = int(res)
        except ValueError:
            raise KeyError("label not found: " + repr(label))
        return res

    def state_indices(self, labels):
        """Same as :meth:`state_index`, but for multiple labels."""
        return [self.state_index(lbl) for lbl in labels]

    def get_op(self, name):
        """Return operator of given name.

        Parameters
        ----------
        name : str
            The name of the operator to be returned.
            In case of multiple operator names separated by whitespace,
            we multiply them together to a single on-site operator
            (with the one on the right acting first).

        Returns
        -------
        op : :class:`~tenpy.linalg.np_conserved`
            The operator given by `name`, with labels ``'p', 'p*'``.
        """
        names = name.split()
        op = getattr(self, names[0])
        for name2 in names[1:]:
            op2 = getattr(self, name2)
            op = npc.tensordot(op, op2, axes=['p*', 'p'])
        return op

    def op_needs_JW(self, name):
        """Wheter an (composite) onsite operator needs a Jordan-Wigner string.

        Parameters
        ----------
        name : str
            The name of the operator, as in :meth:`get_op`.
            In case of multiple operator names separated by whitespace,
            we multiply them together to a single on-site operator
            (with the one on the right acting first).

        Returns
        -------
        needs_JW : bool
            Wheter the operator needs a Jordan-Wigner string, judging from :attr:`need_JW_string`.
        """
        names = name.split()
        need_JW = bool(names[0] in self.need_JW_string)
        for op in names[1:]:
            if op in self.need_JW_string:
                need_JW = not need_JW  # == (need_JW xor (op in self.need_JW_string)
        return need_JW

    def valid_opname(self, name):
        """Check wheter 'name' labels a valid onsite-operator.

        Parameters
        ----------
        name : str
            Label for the operator. Can be multiple operator(labels) separated by whitespace,
            indicating that they should  be multiplied together.

        Returns
        -------
        valid : bool
            ``True`` if `name` is a valid argument to :meth:`get_op`.
        """
        for name2 in name.split():
            if name2 not in self.opnames:
                return False
        return True

    def __repr__(self):
        """Debug representation of self"""
        return "<Site, d={dim:d}, ops={ops!r}>".format(dim=self.dim, ops=self.opnames)


class DoubleSite(Site):
    """Group two :class:`Site` into a larger one.

    A typical use-case is that you want a NearestNeigborModel for TEBD although you have
    next-nearest neighbor interactions: you just double your local Hilbertspace to consist of
    two original sites.
    Note that this is a 'hack' at the cost of other things (e.g., measurements of 'local'
    operators) getting more complicated/computationally expensive.

    If the individual sites indicate fermionic operators (with entries in `needs_JW_string`),
    we construct the new on-site oerators of `site1` to include the JW string of `site0`,
    i.e., we use the Kronecker product of ``[JW, op]`` instead of ``[Id, op]`` if necessary
    (but always ``[op, Id]``).
    In that way the onsite operators of this DoubleSite automatically fulfill the
    expected commutation relations. See also :doc:`../intro_JordanWigner`.

    Parameters
    ----------
    site0 : :class:`Site`
        The first site to be included.
    site1 : :class:`Site`
        The second site to be included.
    label0 : str
        Include the Kronecker product of ``[op, Id]`` as onsite operators with name
        ``opname+label0`` for each of the operators `op` in `site0` (with name `opname`).
    label1 : str
        Include the Kronecker product of ``[Id, op]`` as onsite operators with name
        ``opname+label1`` for each of the operators `op` in `site1` (with name `opname`).
    charges : ``'same'`` | ``'independent' | 'drop'``
        How to handle charges, defaults to 'drop'.
        ``'same'`` means that `site0` and `site1` have the same `ChargeInfo`, and the total charge
        is the sum of the charges on `site0` and `site1`.
        ``'independent'`` means that `site0` and `site1` have possibly different `ChargeInfo`,
        and the charges are conserved separately, i.e., we have two conserved charges.
        For ``'drop'``, we drop any charges, such that the remaining legcharges are trivial.

    Attributes
    ----------
    site0, site1 : :class:`Site`
        The sites from which this is build.
    label0, label1 : str
        The labels which are added to the single-site operators during construction.
    """

    def __init__(self, site0, site1, label0='0', label1='1', charges='drop'):
        if charges == 'drop':
            leg0 = npc.LegCharge.from_drop_charge(site0.leg)
            leg1 = npc.LegCharge.from_drop_charge(site1.leg, chargeinfo=leg0.chinfo)
            perm_qind0, leg0s = leg0.sort()
            perm_qind1, leg1s = leg1.sort()
            site0 = site0.copy_change_charge(leg0, leg0.perm_flat_from_perm_qind(perm_qind0))
            site1 = site1.copy_change_charge(leg1, leg1.perm_flat_from_perm_qind(perm_qind1))
        elif charges == 'same':
            pass  # nothing to do
        elif charges == 'independent':
            # charges are separately conserved
            leg0_triv1 = npc.LegCharge.from_trivial(site0.dim, site1.leg.chinfo)
            leg1_triv0 = npc.LegCharge.from_trivial(site1.dim, site0.leg.chinfo)
            leg0 = npc.LegCharge.from_add_charge(site0.leg, leg0_triv1)
            leg1 = npc.LegCharge.from_add_charge(leg1_triv0, site1.leg, chargeinfo=leg0.chinfo)
            perm_qind0, leg0s = leg0.sort()
            perm_qind1, leg1s = leg1.sort()
            site0 = site0.copy_change_charge(leg0, leg0.perm_flat_from_perm_qind(perm_qind0))
            site1 = site1.copy_change_charge(leg1, leg1.perm_flat_from_perm_qind(perm_qind1))
        else:
            raise ValueError("Unknown option for `charges`: " + repr(charges))
        assert site0.leg.chinfo == site1.leg.chinfo  # check for compatibility
        self.site0 = site0
        self.site1 = site1
        pipe = npc.LegPipe([site0.leg, site1.leg])
        self.leg = pipe  # needed in kroneckerproduct
        states = [None] * pipe.ind_len
        for st0 in site0.state_labels:
            for st1 in site1.state_labels:
                ind_pipe = pipe.map_incoming_flat(
                    [site0.state_labels[st0], site1.state_labels[st1]])
                states[ind_pipe] = ''.join([st0, '_', label0, ' ', st1, '_', label1])
        JW0 = site0.JW
        JW1 = site1.JW
        JW_both = self.kroneckerproduct(JW0, JW1)
        super(DoubleSite, self).__init__(pipe, states, JW=JW_both)
        # add remaining operators
        Id1 = site1.Id
        for opname, op in site0.onsite_ops.items():
            if opname != 'Id':
                need_JW = opname in site0.need_JW_string
                self.add_op(opname + label0, self.kroneckerproduct(op, Id1), need_JW)
        Id0 = site0.Id
        for opname, op in site1.onsite_ops.items():
            if opname != 'Id':
                need_JW = opname in site1.need_JW_string
                op0 = JW0 if need_JW else Id0
                self.add_op(opname + label1, self.kroneckerproduct(op0, op), need_JW)
        # done

    def kroneckerproduct(self, op0, op1):
        r"""Return the Kronecker product :math:`op0 \otimes op1` of local operators.

        Parameters
        ----------
        op0, op1 : :class:`~tenpy.linalg.np_conserved.Array`
            Onsite operators on `site0` and `site1`, respectively.
            Should have labels ``['p', 'p*']``.

        Returns
        -------
        prod : :class:`~tenpy.linalg.np_conserved.Array`
            Kronecker product :math:`op0 \otimes op1`, with labels ``['p', 'p*']``.
        """
        pipe = self.leg
        op = npc.outer(op0.transpose(['p', 'p*']), op1.transpose(['p', 'p*']))
        return op.combine_legs([[0, 2], [1, 3]], qconj=[+1, -1], pipes=[pipe, pipe.conj()])


# ------------------------------------------------------------------------------
# The most common local sites.


class SpinHalfSite(Site):
    r"""Spin-1/2 site.

    Local states are ``up`` (0) and ``down`` (1).
    Local operators are the usual spin-1/2 operators, e.g. ``Sz = [[0.5, 0.], [0., -0.5]]``,
    ``Sx = 0.5*sigma_x`` for the Pauli matrix `sigma_x`.

    ==============  ================================================
    operator        description
    ==============  ================================================
    ``Id, JW``      Identity :math:`\mathbb{1}`
    ``Sx, Sy, Sz``  Spin components :math:`S^{x,y,z}`,
                    equal to half the Pauli matrices.
    ``Sigmax``      Pauli matrix :math:`Sigmax`
    ``Sigmay``
    ``Sigmaz``
    ``Sp, Sm``      Spin flips :math:`S^{\pm} = S^{x} \pm i S^{y}`
    ==============  ================================================

    ============== ====  ============================
    `conserve`     qmod  *excluded* onsite operators
    ============== ====  ============================
    ``'Sz'``       [1]   ``Sx, Sy, Sigmax, Sigmay``
    ``'parity'``   [2]   --
    ``None``       []    --
    ============== ====  ============================

    Parameters
    ----------
    conserve : str
        Defines what is conserved, see table above.

    Attributes
    ----------
    conserve : str
        Defines what is conserved, see table above.
    """

    def __init__(self, conserve='Sz'):
        if conserve not in ['Sz', 'parity', None]:
            raise ValueError("invalid `conserve`: " + repr(conserve))
        Sx = [[0., 0.5], [0.5, 0.]]
        Sy = [[0., -0.5j], [+0.5j, 0.]]
        Sz = [[0.5, 0.], [0., -0.5]]
        Sp = [[0., 1.], [0., 0.]]  # == Sx + i Sy
        Sm = [[0., 0.], [1., 0.]]  # == Sx - i Sy
        ops = dict(Sp=Sp, Sm=Sm, Sz=Sz)
        if conserve == 'Sz':
            chinfo = npc.ChargeInfo([1], ['2*Sz'])
            leg = npc.LegCharge.from_qflat(chinfo, [1, -1])
        else:
            ops.update(Sx=Sx, Sy=Sy)
            if conserve == 'parity':
                chinfo = npc.ChargeInfo([2], ['parity'])
                leg = npc.LegCharge.from_qflat(chinfo, [1, 0])  # ([1, -1] would need ``qmod=[4]``)
            else:
                leg = npc.LegCharge.from_trivial(2)
        self.conserve = conserve
        super(SpinHalfSite, self).__init__(leg, ['up', 'down'], **ops)
        if conserve != 'Sz':
            self.add_op('Sigmax', 2. * self.Sx)
            self.add_op('Sigmay', 2. * self.Sy)
        self.add_op('Sigmaz', 2. * self.Sz)

    def __repr__(self):
        """Debug representation of self"""
        return "SpinHalfSite({c!r})".format(c=self.conserve)


class SpinSite(Site):
    r"""General Spin S site.

    There are `2S+1` local states range from ``down`` (0)  to ``up`` (2S+1),
    corresponding to ``Sz=-S, -S+1, ..., S-1, S``.
    Local operators are the spin-S operators,
    e.g. ``Sz = [[0.5, 0.], [0., -0.5]]``,
    ``Sx = 0.5*sigma_x`` for the Pauli matrix `sigma_x`.

    ==============  ================================================
    operator        description
    ==============  ================================================
    ``Id, JW``      Identity :math:`\mathbb{1}`
    ``Sx, Sy, Sz``  Spin components :math:`S^{x,y,z}`,
                    equal to half the Pauli matrices.
    ``Sp, Sm``      Spin flips :math:`S^{\pm} = S^{x} \pm i S^{y}`
    ==============  ================================================

    ============== ====  ============================
    `conserve`     qmod  *excluded* onsite operators
    ============== ====  ============================
    ``'Sz'``       [1]   ``Sx, Sy``
    ``'parity'``   [2]   --
    ``None``       []    --
    ============== ====  ============================

    Parameters
    ----------
    conserve : str
        Defines what is conserved, see table above.

    Attributes
    ----------
    S : {0.5, 1, 1.5, 2, ...}
        The 2S+1 states range from m = -S, -S+1, ... +S.
    conserve : str
        Defines what is conserved, see table above.
    """

    def __init__(self, S=0.5, conserve='Sz'):
        if conserve not in ['Sz', 'parity', None]:
            raise ValueError("invalid `conserve`: " + repr(conserve))
        self.S = S = float(S)
        d = 2 * S + 1
        if d <= 1:
            raise ValueError("negative S?")
        if np.rint(d) != d:
            raise ValueError("S is not half-integer or integer")
        d = int(d)
        Sz_diag = -S + np.arange(d)
        Sz = np.diag(Sz_diag)
        Sp = np.zeros([d, d])
        for n in np.arange(d - 1):
            # Sp |m> =sqrt( S(S+1)-m(m+1)) |m+1>
            m = n - S
            Sp[n + 1, n] = np.sqrt(S * (S + 1) - m * (m + 1))
        Sm = np.transpose(Sp)
        # Sp = Sx + i Sy, Sm = Sx - i Sy
        Sx = (Sp + Sm) * 0.5
        Sy = (Sm - Sp) * 0.5j
        # Note: For S=1/2, Sy might look wrong compared to the Pauli matrix or SpinHalfSite.
        # Don't worry, I'm 99.99% sure it's correct (J. Hauschild)
        # The reason it looks wrong is simply that this class orders the states as ['down', 'up'],
        # while the usual spin-1/2 convention is ['up', 'down'].
        # (The commutation relations are checked explicitly in `tests/test_site.py`
        ops = dict(Sp=Sp, Sm=Sm, Sz=Sz)
        if conserve == 'Sz':
            chinfo = npc.ChargeInfo([1], ['2*Sz'])
            leg = npc.LegCharge.from_qflat(chinfo, np.array(2 * Sz_diag, dtype=np.int))
        else:
            ops.update(Sx=Sx, Sy=Sy)
            if conserve == 'parity':
                chinfo = npc.ChargeInfo([2], ['parity'])
                leg = npc.LegCharge.from_qflat(chinfo, np.mod(np.arange(d), 2))
            else:
                leg = npc.LegCharge.from_trivial(d)
        self.conserve = conserve
        names = [None] * d
        names[0] = 'down'
        names[-1] = 'up'
        if int(2 * S) % 2 == 0:
            names[int(S)] = '0'
        super(SpinSite, self).__init__(leg, names, **ops)

    def __repr__(self):
        """Debug representation of self"""
        return "SpinSite(S={S!s}, {c!r})".format(S=self.S, c=self.conserve)


class FermionSite(Site):
    r"""Create a :class:`Site` for spin-less fermions.

    Local states are ``empty`` and ``full``.

    .. warning ::
        Using the Jordan-Wigner string (``JW``) is crucial to get correct results,
        otherwise you just describe hardcore bosons!
        Further details in :doc:`../intro_JordanWigner`.

    ==============  ===================================================================
    operator        description
    ==============  ===================================================================
    ``Id``          Identity :math:`\mathbb{1}`
    ``JW``          Sign for the Jordan-Wigner string.
    ``C``           Annihilation operator :math:`c` (up to 'JW'-string left of it)
    ``Cd``          Creation operator :math:`c^\dagger` (up to 'JW'-string left of it)
    ``N``           Number operator :math:`n= c^\dagger c`
    ``dN``          :math:`\delta n := n - filling`
    ``dNdN``        :math:`(\delta n)^2`
    ==============  ===================================================================

    ============== ====  ===============================
    `conserve`     qmod  *exluded* onsite operators
    ============== ====  ===============================
    ``'N'``        [1]   --
    ``'parity'``   [2]   --
    ``None``       []    --
    ============== ====  ===============================

    Parameters
    ----------
    conserve : str
        Defines what is conserved, see table above.
    filling : float
        Average filling. Used to define ``dN``.

    Attributes
    ----------
    conserve : str
        Defines what is conserved, see table above.
    filling : float
        Average filling. Used to define ``dN``.
    """

    def __init__(self, conserve='N', filling=0.5):
        if conserve not in ['N', 'parity', None]:
            raise ValueError("invalid `conserve`: " + repr(conserve))
        JW = np.array([[1., 0.], [0., -1.]])
        C = np.array([[0., 1.], [0., 0.]])
        Cd = np.array([[0., 0.], [1., 0.]])
        N = np.array([[0., 0.], [0., 1.]])
        dN = np.array([[-filling, 0.], [0., 1. - filling]])
        dNdN = dN**2  # (element wise power is fine since dN is diagonal)
        ops = dict(JW=JW, C=C, Cd=Cd, N=N, dN=dN, dNdN=dNdN)
        if conserve == 'N':
            chinfo = npc.ChargeInfo([1], ['N'])
            leg = npc.LegCharge.from_qflat(chinfo, [0, 1])
        elif conserve == 'parity':
            chinfo = npc.ChargeInfo([2], ['parity'])
            leg = npc.LegCharge.from_qflat(chinfo, [0, 1])
        else:
            leg = npc.LegCharge.from_trivial(2)
        self.conserve = conserve
        self.filling = filling
        super(FermionSite, self).__init__(leg, ['empty', 'full'], **ops)
        # specify fermionic operators
        self.need_JW_string |= set(['C', 'Cd'])

    def __repr__(self):
        """Debug representation of self"""
        return "FermionSite({c!r}, {f:f})".format(c=self.conserve, f=self.filling)


class SpinHalfFermionSite(Site):
    r"""Create a :class:`Site` for spinful (spin-1/2) fermions.

    Local states are:
         ``empty``  (vacuum),
         ``up``     (one spin-up electron),
         ``down``   (one spin-down electron), and
         ``full``   (both electrons)

    Local operators can be built from creation operators.

    .. warning ::
        Using the Jordan-Wigner string (``JW``) in the correct way is crucial to get correct
        results, otherwise you just describe hardcore bosons!

    ==============  =============================================================================
    operator        description
    ==============  =============================================================================
    ``Id``          Identity :math:`\mathbb{1}`
    ``JW``          Sign for the Jordan-Wigner string :math:`(-1)^{n_{\uparrow}+n_{\downarrow}}`
    ``JWu``         Partial sign for the Jordan-Wigner string :math:`(-1)^{n_{\uparrow}}`
    ``JWd``         Partial sign for the Jordan-Wigner string :math:`(-1)^{n_{\downarrow}}`
    ``Cu``          Annihilation operator spin-up :math:`c_{\uparrow}`
                    (up to 'JW'-string on sites left of it).
    ``Cdu``         Creation operator spin-up :math:`c^\dagger_{\uparrow}`
                    (up to 'JW'-string on sites left of it).
    ``Cd``          Annihilation operator spin-down :math:`c_{\downarrow}`
                    (up to 'JW'-string on sites left of it).
                    Includes ``JWu`` such that it anti-commutes onsite with ``Cu, Cdu``.
    ``Cdd``         Creation operator spin-down :math:`c^\dagger_{\downarrow}`
                    (up to 'JW'-string on sites left of it).
                    Includes ``JWu`` such that it anti-commutes onsite with ``Cu, Cdu``.
    ``Nu``          Number operator :math:`n_{\uparrow}= c^\dagger_{\uparrow} c_{\uparrow}`
    ``Nd``          Number operator :math:`n_{\downarrow}= c^\dagger_{\downarrow} c_{\downarrow}`
    ``NuNd``        Dotted number operators :math:`n_{\uparrow} n_{\downarrow}`
    ``Ntot``        Total number operator :math:`n_t= n_{\uparrow} + n_{\downarrow}`
    ``dN``          Total number operator compared to the filling :math:`\Delta n = n_t-filling`
    ``Sx, Sy, Sz``  Spin operators :math:`S^{x,y,z}`, in particular
                    :math:`S^z = \frac{1}{2}( n_\uparrow - n_\downarrow )`
    ``Sp, Sm``      Spin flips :math:`S^{\pm} = S^{x} \pm i S^{y}`,
                    e.g. :math:`S^{+} = c^\dagger_\uparrow c_\downarrow`
    ==============  =============================================================================

    The spin operators are defined as :math:`S^\gamma =
    (c^\dagger_{\uparrow}, c^\dagger_{\downarrow}) \sigma^\gamma (c_{\uparrow}, c_{\downarrow})^T`,
    where :math:`\sigma^\gamma` are spin-1/2 matrices (i.e. half the pauli matrices).

    ============= ============= ======= =======================================
    `cons_N`      `cons_Sz`     qmod    *excluded* onsite operators
    ============= ============= ======= =======================================
    ``'N'``       ``'Sz'``      [1, 1]  ``Sx, Sy``
    ``'N'``       ``'parity'``  [1, 2]  --
    ``'N'``       ``None``      [1]     --
    ``'parity'``  ``'Sz'``      [2, 1]  ``Sx, Sy``
    ``'parity'``  ``'parity'``  [2, 2]  --
    ``'parity'``  ``None``      [2]     --
    ``None``      ``'Sz'``      [1]     ``Sx, Sy``
    ``None``      ``'parity'``  [2]     --
    ``None``      ``None``      []      --
    ============= ============= ======= =======================================

    .. todo ::
        Check if Jordan-Wigner strings for 4x4 operators are correct.

    Parameters
    ----------
    cons_N : ``'N' | 'parity' | None``
        Whether particle number is conserved, c.f. table above.
    cons_Sz : ``'Sz' | 'parity' | None``
        Whether spin is conserved, c.f. table above.
    filling : float
        Average filling. Used to define ``dN``.

    Attributes
    ----------
    cons_N : ``'N' | 'parity' | None``
        Whether particle number is conserved, c.f. table above.
    cons_Sz : ``'Sz' | 'parity' | None``
        Whether spin is conserved, c.f. table above.
    filling : float
        Average filling. Used to define ``dN``.
    """

    def __init__(self, cons_N='N', cons_Sz='Sz', filling=1.):
        if cons_N not in ['N', 'parity', None]:
            raise ValueError("invalid `cons_N`: " + repr(cons_N))
        if cons_Sz not in ['Sz', 'parity', None]:
            raise ValueError("invalid `cons_Sz`: " + repr(cons_Sz))
        d = 4
        states = ['empty', 'up', 'down', 'full']
        # 0) Build the operators.
        Nu_diag = np.array([0., 1., 0., 1.], dtype=np.float)
        Nd_diag = np.array([0., 0., 1., 1.], dtype=np.float)
        Nu = np.diag(Nu_diag)
        Nd = np.diag(Nd_diag)
        Ntot = np.diag(Nu_diag + Nd_diag)
        dN = np.diag(Nu_diag + Nd_diag - filling)
        NuNd = np.diag(Nu_diag * Nd_diag)
        JWu = np.diag(1. - 2 * Nu_diag)  # (-1)^Nu
        JWd = np.diag(1. - 2 * Nd_diag)  # (-1)^Nd
        JW = JWu * JWd  # (-1)^{Nu+Nd}

        Cu = np.zeros((d, d))
        Cu[0, 1] = Cu[2, 3] = 1
        Cdu = np.transpose(Cu)
        # For spin-down annihilation operator: include a Jordan-Wigner string JWu
        # this ensures that Cdu.Cd = - Cd.Cdu
        # c.f. the chapter on the Jordan-Wigner trafo in the userguide
        Cd_noJW = np.zeros((d, d))
        Cd_noJW[0, 2] = Cd_noJW[1, 3] = 1
        Cd = np.dot(JWu, Cd_noJW)  # (don't do this for spin-up...)
        Cdd = np.transpose(Cd)

        # spin operators are defined as  (Cdu, Cdd) S^gamma (Cu, Cd)^T,
        # where S^gamma is the 2x2 matrix for spin-half
        Sz = np.diag(0.5 * (Nu_diag - Nd_diag))
        Sp = np.dot(Cdu, Cd)
        Sm = np.dot(Cdd, Cu)
        Sx = 0.5 * (Sp + Sm)
        Sy = -0.5j * (Sp - Sm)

        ops = dict(JW=JW, JWu=JWu, JWd=JWd,
                   Cu=Cu, Cdu=Cdu, Cd=Cd, Cdd=Cdd,
                   Nu=Nu, Nd=Nd, Ntot=Ntot, NuNd=NuNd, dN=dN,
                   Sx=Sx, Sy=Sy, Sz=Sz, Sp=Sp, Sm=Sm)  # yapf: disable

        # handle charges
        qmod = []
        qnames = []
        charges = []
        if cons_N == 'N':
            qnames.append('N')
            qmod.append(1)
            charges.append([0, 1, 1, 2])
        elif cons_N == 'parity':
            qnames.append('N')
            qmod.append(2)
            charges.append([0, 1, 1, 0])
        if cons_Sz == 'Sz':
            qnames.append('Sz')
            qmod.append(1)
            charges.append([0, 1, -1, 0])
            del ops['Sx']
            del ops['Sy']
        elif cons_Sz == 'parity':
            qnames.append('Sz')
            qmod.append(4)  # difference between up and down is 2!
            charges.append([0, 1, 3, 0])  # == [0, 1, -1, 0] mod 4
            # chosen s.t. Cu, Cd have well-defined charges!

        if len(qmod) == 0:
            leg = npc.LegCharge.from_trivial(d)
        else:
            if len(qmod) == 1:
                charges = charges[0]
            else:  # len(charges) == 2: need to transpose
                charges = [[q1, q2] for q1, q2 in zip(charges[0], charges[1])]
            chinfo = npc.ChargeInfo(qmod, qnames)
            leg_unsorted = npc.LegCharge.from_qflat(chinfo, charges)
            # sort by charges
            perm_qind, leg = leg_unsorted.sort()
            perm_flat = leg_unsorted.perm_flat_from_perm_qind(perm_qind)
            self.perm = perm_flat
            # permute operators accordingly
            for opname in ops:
                ops[opname] = ops[opname][np.ix_(perm_flat, perm_flat)]
            # and the states
            states = [states[i] for i in perm_flat]
        self.cons_N = cons_N
        self.cons_Sz = cons_Sz
        super(SpinHalfFermionSite, self).__init__(leg, states, **ops)
        # specify fermionic operators
        self.need_JW_string |= set(['Cu', 'Cdu', 'Cd', 'Cdd'])

    def __repr__(self):
        """Debug representation of self"""
        return "SpinHalfFermionSite({c!r})".format(c=self.conserve)


class BosonSite(Site):
    r"""Create a :class:`Site` for up to `Nmax` bosons.

    Local states are ``vac, 1, 2, ... , Nc``.
    (Exception: for parity conservation, we sort as ``vac, 2, 4, ..., 1, 3, 5, ...``.)

    ==============  ========================================
    operator        description
    ==============  ========================================
    ``Id, JW``      Identity :math:`\mathbb{1}`
    ``B``           Annihilation operator :math:`b`
    ``Bd``          Creation operator :math:`b^\dagger`
    ``N``           Number operator :math:`n= b^\dagger b`
    ``NN``          :math:`n^2`
    ``dN``          :math:`\delta n := n - filling`
    ``dNdN``        :math:`(\delta n)^2`
    ``P``           Parity :math:`Id - 2 (n \mod 2)`.
    ==============  ========================================

    ============== ====  ==================================
    `conserve`     qmod  *excluded* onsite operators
    ============== ====  ==================================
    ``'N'``        [1]   --
    ``'parity'``   [2]   --
    ``None``       []    --
    ============== ====  ==================================

    Parameters
    ----------
    Nmax : int
        Cutoff defining the maximum number of bosons per site.
        The default ``Nmax=1`` describes hard-core bosons.
    conserve : str
        Defines what is conserved, see table above.
    filling : float
        Average filling. Used to define ``dN``.

    Attributes
    ----------
    conserve : str
        Defines what is conserved, see table above.
    filling : float
        Average filling. Used to define ``dN``.
    """

    def __init__(self, Nmax=1, conserve='N', filling=0.):
        if conserve not in ['N', 'parity', None]:
            raise ValueError("invalid `conserve`: " + repr(conserve))
        dim = Nmax + 1
        states = ['vac'] + [str(n) for n in range(1, dim)]
        if dim < 2:
            raise ValueError("local dimension should be larger than 1....")
        B = np.zeros([dim, dim], dtype=np.float)  # destruction/annihilation operator
        for n in range(1, dim):
            B[n - 1, n] = np.sqrt(n)
        Bd = np.transpose(B)  # .conj() wouldn't do anything
        # Note: np.dot(Bd, B) has numerical roundoff errors of eps~=4.4e-16.
        Ndiag = np.arange(dim, dtype=np.float)
        N = np.diag(Ndiag)
        NN = np.diag(Ndiag**2)
        dN = np.diag(Ndiag - filling)
        dNdN = np.diag((Ndiag - filling)**2)
        P = np.diag(1. - 2. * np.mod(Ndiag, 2))
        ops = dict(B=B, Bd=Bd, N=N, NN=NN, dN=dN, dNdN=dNdN, P=P)
        if conserve == 'N':
            chinfo = npc.ChargeInfo([1], ['N'])
            leg = npc.LegCharge.from_qflat(chinfo, range(dim))
        elif conserve == 'parity':
            chinfo = npc.ChargeInfo([2], ['parity'])
            leg_unsorted = npc.LegCharge.from_qflat(chinfo, [i % 2 for i in range(dim)])
            # sort by charges
            perm_qind, leg = leg_unsorted.sort()
            perm_flat = leg_unsorted.perm_flat_from_perm_qind(perm_qind)
            self.perm = perm_flat
            # permute operators accordingly
            for opname in ops:
                ops[opname] = ops[opname][np.ix_(perm_flat, perm_flat)]
            # and the states
            states = [states[i] for i in perm_flat]
        else:
            leg = npc.LegCharge.from_trivial(dim)
        self.Nmax = Nmax
        self.conserve = conserve
        self.filling = filling
        super(BosonSite, self).__init__(leg, states, **ops)

    def __repr__(self):
        """Debug representation of self"""
        return "BosonSite({N:d}, {c!r}, {f:f})".format(
            N=self.Nmax, c=self.conserve, f=self.filling)
