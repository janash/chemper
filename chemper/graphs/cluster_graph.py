"""
fragment_graph.py

ChemPerGraph are a class for tracking molecular fragments based on information about the atoms and bonds they contain.
You can combine them or take a difference in order to find distinguishing characteristics in a set of clustered
molecular sub-graphs.

AUTHORS:

Caitlin C. Bannan <bannanc@uci.edu>, Mobley Group, University of California Irvine
"""

# TODO: import mol_toolkit?
import networkx as nx


class ClusterGraph(object):
    """
    ChemPerGraphs are a graph based class for storing atom and bond information.
    They use the chemper.mol_toolkits Atoms, Bonds, and Mols
    """
    class AtomStorage(object):
        """
        AtomStorage tracks information about an atom
        """
        def __init__(self, atoms=None, smirks_index=None):
            """
            """
            self.decorators = set()
            if atoms is not None:
                for atom in atoms:
                    self.decorators.add(self._make_atom_decorators(atom))
            self.smirks_index = smirks_index

        def _make_atom_decorators(self, atom):
            aromatic = 'a' if atom.is_aromatic() else 'A'
            charge = atom.formal_charge()
            if charge >= 0:
                charge = '+%i' % charge
            else:
                charge = '%i' % charge

            return (
                '#%i' % atom.atomic_number(),
                aromatic,
                'H%i' % atom.hydrogen_count(),
                'X%i' % atom.connectivity(),
                'x%i' % atom.ring_connectivity(),
                'r%i' % atom.min_ring_size(),
                charge
                )

        def as_smirks(self):
            """
            :return: smirks pattern for this atom
            """
            if len(self.decorators) == 0:
                if self.smirks_index is None or self.smirks_index <= 0:
                    return '[*]'
                return '[*:%i]' % self.smirks_index

            base_smirks = ','.join([''.join(l) for l in sorted(list(self.decorators))])
            if self.smirks_index is None or self.smirks_index <= 0:
                return '[%s]' % base_smirks

            return '[%s:%i]' % (base_smirks, self.smirks_index)

        def add_atom(self, atom):
            self.decorators.add(self._make_atom_decorators(atom))

    class BondStorage(object):
        """
        BondStorage tracks information about a bond
        """
        def __init__(self, bonds=None, smirks_index=None):
            self.order = set()
            self.ring = set()
            self.order_dict = {1:'-', 1.5:':', 2:'=', 3:'#'}
            if bonds is not None:
                for bond in bonds:
                    self.order.add(self.order_dict.get(bond.get_order()))
                    self.ring.add(bond.is_ring())

            self.smirks_index = smirks_index

        def as_smirks(self):
            """
            :return: string of how this bond should appear in a SMIRKS string
            """
            if len(self.order) == 0:
                order = '~'
            else:
                order = ','.join(sorted(list(self.order)))

            if len(self.ring) == 1:
                if list(self.ring)[0]:
                    return order+';@'
                else:
                    return order+';!@'

            return order

        def add_bond(self, bond):
            """
            adds decorators for another bond
            :param bond: chemper mol_toolkit Bond object
            """
            self.order.add(self.order_dict.get(bond.get_order()))
            self.ring.add(bond.is_ring())

    # Initiate ClusterGraph
    def __init__(self, mols=None, smirks_atoms_list=None, layers=0):
        # TODO: figure out layers, currently only supporting layers=0
        """
        Initialize a ChemPerGraph from a molecule and a set of indexed atoms

        :param mols: list of chemper mols
        :param smirks_atoms_list: sorted by mol list of dictionary of the form {smirks_index: atom_index}
        :param layers: how many atoms out from the smirks indexed atoms do you wish save (default=0)
                       'all' will lead to all atoms in the molecule being specified (not recommended)
        """
        self._graph = nx.Graph()
        self.atom_by_smirks_index = dict() # stores a dictionary of atoms with smirks_index
        self.bond_by_smirks_index = dict()
        self.mols = list()
        self.smirks_atoms_list = list()

        if mols is not None:
            if len(mols) != len(smirks_atoms_list):
                raise Exception('Number of molecules and smirks dictionaries should be equal')

            self._add_first_smirks_atoms(mols[0], smirks_atoms_list[0])
            for idx, mol in enumerate(mols[1:]):
                self.add_mol(mol, smirks_atoms_list[idx])

        # TODO: figure out how to extend beyond just "SMIRKS indexed" atoms
        # self.atom_by_index = dict()
        #for smirks_key, atom_storage in self.atom_by_smirks_index.items():
        #    self._add_layers(atom_storage, layers)

    def _add_first_smirks_atoms(self, mol, smirks_atoms):
        self.mols.append(mol)
        self.smirks_atoms_list.append(smirks_atoms)

        # add all smirks atoms to the graph
        for key, atom_index in smirks_atoms.items():
            atom1 = mol.get_atom_by_index(atom_index)
            new_atom_storage = self.AtomStorage([atom1], key)
            self._graph.add_node(new_atom_storage)
            self.atom_by_smirks_index[key] = new_atom_storage
            # self.atom_by_index[atom_index] = new_atom_storage

            # Check for bonded atoms already in the graph
            for neighbor_key, neighbor_index in smirks_atoms.items():
                if not neighbor_key in self.atom_by_smirks_index:
                    continue
                atom2 = mol.get_atom_by_index(neighbor_index)
                bond = mol.get_bond_by_atoms(atom1, atom2)

                if bond is not None: # Atoms are connected add edge
                    bond_smirks = max(neighbor_key, key)-1
                    bond_storage = self.BondStorage([bond], bond_smirks)
                    self.bond_by_smirks_index[bond_smirks] = bond_storage
                    self._graph.add_edge(new_atom_storage,
                                         self.atom_by_smirks_index[neighbor_key],
                                         bond=bond_storage)

    def add_mol(self, mol, smirks_atoms):
        """
        :param mol:
        :param smirks_atoms:
        :return:
        """
        self.mols.append(mol)
        self.smirks_atoms_list.append(smirks_atoms)

        for key, atom_index in smirks_atoms.items():
            atom1 = mol.get_atom_by_index(atom_index)
            self.atom_by_smirks_index[key].add_atom(atom1)

            for neighbor_key, neighbor_index in smirks_atoms.items():
                # check for connecting bond
                atom2 = mol.get_atom_by_index(neighbor_index)
                bond = mol.get_bond_by_atoms(atom1, atom2)
                if bond is not None:
                    bond_smirks = max(neighbor_key, key) - 1
                    self.bond_by_smirks_index[bond_smirks].add_bond(bond)

    def as_smirks(self):
        """
        :return: a SMIRKS string matching the exact atom and bond information stored
        """

        # If no atoms have been added
        if len(self._graph.nodes()) == 0:
            return None

        if self.atom_by_smirks_index:
            min_smirks = min(self.atom_by_smirks_index)
            init_atom = self.atom_by_smirks_index[min_smirks]
        else:
            init_atom = self.get_atoms()[0]

        # sort neighboring atoms to keep consist output
        neighbors = sorted(self.get_neighbors(init_atom), key=lambda a: a.as_smirks())
        return self._as_smirks(init_atom, neighbors)

    def _as_smirks(self, init_atom, neighbors):

        smirks = init_atom.as_smirks()

        for idx, neighbor in enumerate(neighbors):
            bond = self.get_connecting_bond(init_atom, neighbor)
            bond_smirks = bond.as_smirks()

            new_neighbors = self.get_neighbors(neighbor)
            new_neighbors.remove(init_atom)

            atom_smirks = self._as_smirks(neighbor, new_neighbors)

            if idx < len(neighbors) - 1:
                smirks += '(' + bond_smirks + atom_smirks + ')'
            else:
                smirks += bond_smirks + atom_smirks

        return smirks

    def get_atoms(self):
        """
        :return: list of all AtomStorage objects in graph
        """
        return list(self._graph.nodes())

    def get_connecting_bond(self, atom1, atom2):
        """
        :param atom1: AtomStorage object in this graph
        :param atom2: AtomStorage object in this graph
        :return: bond connecting them
        """
        return self._graph.get_edge_data(atom1, atom2)['bond']

    def get_bonds(self):
        """
        :return: list of all BondStorage objects in graph
        """
        # TODO, this currently returns edges, not bond objects
        return [data['bond'] for a1, a2, data in self._graph.edges(data=True)]

    def get_neighbors(self, atom):
        """
        :param atom: an AtomStorage object
        :return: neighboring AtomStorage objects
        """
        return list(self._graph.neighbors(atom))

    def add_atom(self, new_atoms, new_bonds=None, bond_to_atom=None,
                 new_smirks_index=None, new_bond_index=None):
        """
        :param new_atoms: a list of chemper mol_toolkit atom object
        :param new_bonds: a list of chemper mol_toolkit bond object
        :param bond_to_atom: AtomStorage object to connect this bond to
        :param new_smirks_index: integer for SMIRKS indexing the new atom
        :param new_bond_index: integer for 'smirks_index' on bond storage object
        :return: new AtomStorage object or None if atom wasn't added
        """
        if bond_to_atom is None and len(self.get_atoms()) > 0:
            return None

        new_atom_storage = self.AtomStorage(new_atoms, smirks_index=new_smirks_index)
        self._graph.add_node(new_atom_storage)
        if new_smirks_index is not None:
            self.atom_by_smirks_index[new_smirks_index] = new_atom_storage

        # This is the first atom added to the graph
        if bond_to_atom is None:
            return new_atom_storage

        new_bond_storage = self.BondStorage(new_bonds, new_bond_index)
        self.bond_by_smirks_index[new_bond_index] = new_bond_storage

        self._graph.add_edge(bond_to_atom, new_atom_storage, bond = new_bond_storage)
        return new_atom_storage
