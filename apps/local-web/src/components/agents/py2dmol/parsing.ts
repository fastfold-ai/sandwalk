import type { Atom, FrameData } from './types';

const RESIDUE_TO_ONE_LETTER: Record<string, string> = {
  ALA: 'A', ARG: 'R', ASN: 'N', ASP: 'D', CYS: 'C', GLN: 'Q', GLU: 'E', GLY: 'G',
  HIS: 'H', ILE: 'I', LEU: 'L', LYS: 'K', MET: 'M', PHE: 'F', PRO: 'P', SER: 'S',
  THR: 'T', TRP: 'W', TYR: 'Y', VAL: 'V',
  A: 'A', C: 'C', G: 'G', U: 'U', T: 'T',
  DA: 'A', DC: 'C', DG: 'G', DT: 'T',
  RA: 'A', RC: 'C', RG: 'G', RU: 'U',
};

function residueToOneLetter(resName: string): string {
  const key = String(resName || '').trim().toUpperCase();
  return RESIDUE_TO_ONE_LETTER[key] || (key[0] || 'X');
}

export function parsePDB(text: string): Atom[][] {
  const models: Atom[][] = []; let currentModelAtoms: Atom[] = []; const lines = text.split('\n');
  for (const line of lines) {
    if (line.startsWith('MODEL')) { if (currentModelAtoms.length > 0) { models.push(currentModelAtoms); } currentModelAtoms = []; }
    if (line.startsWith('ATOM') || line.startsWith('HETATM')) {
      currentModelAtoms.push({
        record: line.substring(0, 6).trim(),
        atomName: line.substring(12, 16).trim(),
        resName: line.substring(17, 20).trim(),
        chain: line.substring(21, 22).trim(),
        resSeq: parseInt(line.substring(22, 26)),
        x: parseFloat(line.substring(30, 38)),
        y: parseFloat(line.substring(38, 46)),
        z: parseFloat(line.substring(46, 54)),
        b: parseFloat(line.substring(60, 66)),
        element: line.substring(76, 78).trim()
      });
    }
    if (line.startsWith('ENDMDL')) { if (currentModelAtoms.length > 0) { models.push(currentModelAtoms); currentModelAtoms = []; } }
  }
  if (currentModelAtoms.length > 0) models.push(currentModelAtoms);
  if (models.length === 0 && currentModelAtoms.length > 0) models.push(currentModelAtoms);
  return models;
}

const CIF_TOKEN_RE = /(?:[^\s"']+|"([^"]*)"|'([^']*)')+/g

function tokenizeCifLine(line: string): string[] {
  return line.match(CIF_TOKEN_RE) || []
}

/**
 * OpenFold / ModelCIF often wraps long _atom_site rows onto the next line
 * (e.g. the model number alone). Merge continuations until column count matches.
 */
function readCifRow(
  lines: string[],
  start: number,
  columnCount: number
): { values: string[]; next: number } | null {
  let values: string[] = []
  let index = start
  while (index < lines.length && values.length < columnCount) {
    const line = lines[index]
    if (
      !line ||
      line.startsWith('#') ||
      line.startsWith('loop_') ||
      line.startsWith('_') ||
      line.startsWith(';')
    ) {
      break
    }
    values = values.concat(tokenizeCifLine(line))
    index += 1
  }
  if (values.length < columnCount) return null
  return { values: values.slice(0, columnCount), next: index }
}

export function parseCIF(text: string): Atom[][] {
  const modelMap = new Map<number, Atom[]>()
  const lines = text.split('\n')
  const headers: string[] = []
  const headerMap: Record<string, number> = {}
  let modelIDKey: string | null = null
  let modelID = 1

  for (const line of lines) {
    if (line.startsWith('_atom_site.')) {
      const header = line.trim()
      headerMap[header] = headers.length
      headers.push(header)
      if (header.includes('model_no') || header.includes('pdbx_PDB_model_num')) {
        modelIDKey = header
      }
    } else if (
      headers.length > 0 &&
      (line.startsWith('loop_') || line.startsWith('#'))
    ) {
      break
    }
  }
  if (headers.length === 0) return []

  let atomSiteStart = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith('_atom_site.')) {
      atomSiteStart = i
      break
    }
  }
  if (atomSiteStart < 0) return []

  let rowStart = atomSiteStart
  while (rowStart < lines.length && lines[rowStart].startsWith('_atom_site.')) {
    rowStart += 1
  }

  let cursor = rowStart
  while (cursor < lines.length) {
    const line = lines[cursor]
    if (line.startsWith('#') || line.startsWith('loop_') || line.startsWith('_')) {
      break
    }
    if (!line.trim() || line.startsWith(';')) {
      cursor += 1
      continue
    }
    const row = readCifRow(lines, cursor, headers.length)
    if (!row) {
      cursor += 1
      continue
    }
    cursor = row.next
    const values = row.values
    const getString = (key: string) => values[headerMap[key]] || '?'
    const getFloat = (key: string) => parseFloat(values[headerMap[key]]) || 0.0
    const getInt = (key: string) => parseInt(values[headerMap[key]], 10) || 0
    const atomNameRaw = getString('_atom_site.label_atom_id')
    let atomName = atomNameRaw
    if (atomName.length > 1 && atomName.startsWith("'") && atomName.endsWith("'")) {
      atomName = atomName.substring(1, atomName.length - 1)
    } else if (
      atomName.length > 1 &&
      atomName.startsWith('"') &&
      atomName.endsWith('"')
    ) {
      atomName = atomName.substring(1, atomName.length - 1)
    }
    const atom: Atom = {
      record: getString('_atom_site.group_PDB'),
      atomName,
      resName: getString('_atom_site.label_comp_id'),
      chain: getString('_atom_site.auth_asym_id'),
      resSeq: getInt('_atom_site.auth_seq_id'),
      x: getFloat('_atom_site.Cartn_x'),
      y: getFloat('_atom_site.Cartn_y'),
      z: getFloat('_atom_site.Cartn_z'),
      b: getFloat('_atom_site.B_iso_or_equiv'),
      element: getString('_atom_site.type_symbol')
    }
    if (modelIDKey) modelID = getInt(modelIDKey)
    if (!modelMap.has(modelID)) modelMap.set(modelID, [])
    modelMap.get(modelID)!.push(atom)
  }

  return Array.from(modelMap.keys())
    .sort((a, b) => a - b)
    .map(id => modelMap.get(id)!) as Atom[][]
}

export function convertParsedToFrameData(atoms: Atom[]): FrameData {
  const coords: number[][] = [], plddts: number[] = [], atom_chains: string[] = [], atom_types: string[] = [];
  const position_names: string[] = [], residue_numbers: number[] = [];
  const rna_bases = ['A','C','G','U','RA','RC','RG','RU'];
  const proteinResidues = new Set(["ALA","ARG","ASN","ASP","CYS","GLU","GLN","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"]);
  const nucleicResidues = new Set(["A","C","G","U","T","DA","DC","DG","DT","RA","RC","RG","RU"]);
  const residues = new Map<string, { atoms: Atom[]; resName: string; chain: string; record: string }>();
  for (const atom of atoms) {
    if (atom.resName === 'HOH') continue;
    const resKey = `${atom.chain}:${atom.resSeq}:${atom.resName}`;
    if (!residues.has(resKey)) { residues.set(resKey, { atoms: [], resName: atom.resName, chain: atom.chain, record: atom.record }); }
    residues.get(resKey)!.atoms.push(atom);
  }
  for (const [, residue] of residues.entries()) {
    const is_protein = proteinResidues.has(residue.resName);
    const is_nucleic = nucleicResidues.has(residue.resName);
    if (is_protein) {
      const ca = residue.atoms.find(a => a.atomName === 'CA');
      if (ca) {
        coords.push([ca.x,ca.y,ca.z]); plddts.push(ca.b); atom_chains.push(ca.chain); atom_types.push('P');
        position_names.push(residueToOneLetter(residue.resName)); residue_numbers.push(ca.resSeq);
      }
    } else if (is_nucleic) {
      let c4_atom = residue.atoms.find(a => a.atomName === "C4'" || a.atomName === "C4*");
      if (c4_atom) {
        coords.push([c4_atom.x,c4_atom.y,c4_atom.z]); plddts.push(c4_atom.b); atom_chains.push(c4_atom.chain); atom_types.push(rna_bases.includes(residue.resName) || residue.resName.startsWith('R') ? 'R' : 'D');
        position_names.push(residueToOneLetter(residue.resName)); residue_numbers.push(c4_atom.resSeq);
      }
    } else if (residue.record === 'HETATM') {
      for (const atom of residue.atoms) {
        if (atom.element !== 'H' && atom.element !== 'D') {
          coords.push([atom.x,atom.y,atom.z]); plddts.push(atom.b); atom_chains.push(atom.chain); atom_types.push('L');
          position_names.push(residueToOneLetter(residue.resName)); residue_numbers.push(atom.resSeq);
        }
      }
    }
  }
  return { coords, plddts, chains: atom_chains, atom_types, position_names, residue_numbers };
}

export type TrajectorySelectionTemplate = {
  indices: number[];
  chains: string[];
  atom_types: string[];
  plddts: number[];
  position_names: string[];
  residue_numbers: number[];
};

export function buildTrajectorySelectionTemplate(atoms: Atom[]): TrajectorySelectionTemplate {
  const indices: number[] = [];
  const chains: string[] = [];
  const atom_types: string[] = [];
  const plddts: number[] = [];
  const position_names: string[] = [];
  const residue_numbers: number[] = [];
  const rna_bases = ['A','C','G','U','RA','RC','RG','RU'];
  const proteinResidues = new Set(["ALA","ARG","ASN","ASP","CYS","GLU","GLN","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"]);
  const nucleicResidues = new Set(["A","C","G","U","T","DA","DC","DG","DT","RA","RC","RG","RU"]);
  const residues = new Map<string, { atomIndices: number[]; resName: string; chain: string; record: string }>();

  for (let atomIdx = 0; atomIdx < atoms.length; atomIdx++) {
    const atom = atoms[atomIdx];
    if (atom.resName === 'HOH') continue;
    const resKey = `${atom.chain}:${atom.resSeq}:${atom.resName}`;
    if (!residues.has(resKey)) {
      residues.set(resKey, { atomIndices: [], resName: atom.resName, chain: atom.chain, record: atom.record });
    }
    residues.get(resKey)!.atomIndices.push(atomIdx);
  }

  for (const [, residue] of residues.entries()) {
    const is_protein = proteinResidues.has(residue.resName);
    const is_nucleic = nucleicResidues.has(residue.resName);
    if (is_protein) {
      let picked: number | null = null;
      for (const idx of residue.atomIndices) {
        if (atoms[idx].atomName === 'CA') { picked = idx; break; }
      }
      if (picked != null) {
        indices.push(picked);
        plddts.push(atoms[picked].b);
        chains.push(atoms[picked].chain);
        atom_types.push('P');
        position_names.push(residueToOneLetter(residue.resName));
        residue_numbers.push(atoms[picked].resSeq);
      }
    } else if (is_nucleic) {
      let picked: number | null = null;
      for (const idx of residue.atomIndices) {
        const an = atoms[idx].atomName;
        if (an === "C4'" || an === 'C4*') { picked = idx; break; }
      }
      if (picked != null) {
        indices.push(picked);
        plddts.push(atoms[picked].b);
        chains.push(atoms[picked].chain);
        atom_types.push(rna_bases.includes(residue.resName) || residue.resName.startsWith('R') ? 'R' : 'D');
        position_names.push(residueToOneLetter(residue.resName));
        residue_numbers.push(atoms[picked].resSeq);
      }
    } else if (residue.record === 'HETATM') {
      for (const idx of residue.atomIndices) {
        const atom = atoms[idx];
        if (atom.element !== 'H' && atom.element !== 'D') {
          indices.push(idx);
          plddts.push(atom.b);
          chains.push(atom.chain);
          atom_types.push('L');
          position_names.push(residueToOneLetter(residue.resName));
          residue_numbers.push(atom.resSeq);
        }
      }
    }
  }

  return { indices, chains, atom_types, plddts, position_names, residue_numbers };
}

export function buildFrameDataFromTrajectoryCoordinates(
  x: Float32Array,
  y: Float32Array,
  z: Float32Array,
  template: TrajectorySelectionTemplate
): FrameData {
  const coords: number[][] = [];
  for (const atomIndex of template.indices) {
    if (atomIndex < 0 || atomIndex >= x.length || atomIndex >= y.length || atomIndex >= z.length) continue;
    coords.push([x[atomIndex], y[atomIndex], z[atomIndex]]);
  }
  return {
    coords,
    plddts: [...template.plddts],
    chains: [...template.chains],
    atom_types: [...template.atom_types],
    position_names: [...template.position_names],
    residue_numbers: [...template.residue_numbers],
  };
}

function readInt32(view: DataView, offset: number, littleEndian: boolean) {
  return view.getInt32(offset, littleEndian);
}

function readFloat32Array(view: DataView, start: number, count: number, littleEndian: boolean) {
  const out = new Float32Array(count);
  let p = start;
  for (let i = 0; i < count; i++) {
    out[i] = view.getFloat32(p, littleEndian);
    p += 4;
  }
  return out;
}

export type DcdFrame = { x: Float32Array; y: Float32Array; z: Float32Array };
export type ParsedDcd = { natoms: number; frames: DcdFrame[] };

export function parseDcd(arrayBuffer: ArrayBuffer): ParsedDcd {
  const view = new DataView(arrayBuffer);
  let littleEndian = true;
  let offset = 0;

  const detectEndian = () => {
    const le = view.getInt32(0, true);
    const be = view.getInt32(0, false);
    if (le > 0 && le < 10000) return true;
    if (be > 0 && be < 10000) return false;
    return true;
  };
  littleEndian = detectEndian();

  const readRecord = () => {
    if (offset + 8 > view.byteLength) throw new Error('Unexpected EOF while reading DCD record');
    const size = readInt32(view, offset, littleEndian);
    const start = offset + 4;
    const end = start + size;
    const trailerPos = end;
    if (trailerPos + 4 > view.byteLength) throw new Error('Corrupt DCD record bounds');
    const trailer = readInt32(view, trailerPos, littleEndian);
    if (trailer !== size) throw new Error('DCD record marker mismatch');
    offset = trailerPos + 4;
    return { start, size };
  };

  // Header record (must begin with CORD)
  const header = readRecord();
  if (header.size < 84) throw new Error('Invalid DCD header');
  const magic = String.fromCharCode(
    view.getUint8(header.start + 0),
    view.getUint8(header.start + 1),
    view.getUint8(header.start + 2),
    view.getUint8(header.start + 3),
  );
  if (magic !== 'CORD') throw new Error(`Unsupported DCD magic: ${magic}`);
  readInt32(view, header.start + 4, littleEndian); // nset
  readInt32(view, header.start + 44, littleEndian); // namnf (fixed atoms)

  // Title record
  const title = readRecord();
  if (title.size < 4) throw new Error('Invalid DCD title record');

  // NATOMS record
  const natomsRec = readRecord();
  if (natomsRec.size !== 4) throw new Error('Invalid DCD natoms record');
  const natoms = readInt32(view, natomsRec.start, littleEndian);
  if (!Number.isFinite(natoms) || natoms <= 0) throw new Error('Invalid DCD natoms value');
  // Some valid CHARMM/OpenMM DCD files set NAMNF > 0 while still storing
  // full coordinate blocks for every atom in each frame. Rejecting on NAMNF
  // causes valid trajectories to fallback to static 1/1 rendering.
  const expectedBytes = natoms * 4;

  const frames: DcdFrame[] = [];
  while (offset < view.byteLength) {
    // Optional unit cell block (typically size 48 bytes in CHARMM DCDs)
    if (offset + 8 > view.byteLength) break;
    const maybeSize = readInt32(view, offset, littleEndian);
    // IMPORTANT: only treat as unit-cell when it is not a coordinate block size.
    // Some coarse-grained trajectories have natoms*4 === 56, which previously got
    // misclassified as a unit cell and collapsed playback to 1 frame.
    if ((maybeSize === 48 || maybeSize === 56) && maybeSize !== expectedBytes) {
      const maybeTrailerPos = offset + 4 + maybeSize;
      if (maybeTrailerPos + 4 <= view.byteLength) {
        const maybeTrailer = readInt32(view, maybeTrailerPos, littleEndian);
        if (maybeTrailer === maybeSize) {
          readRecord(); // consume unit cell
        }
      }
    }

    if (offset >= view.byteLength) break;
    const xRec = readRecord();
    const yRec = readRecord();
    const zRec = readRecord();
    if (xRec.size !== expectedBytes || yRec.size !== expectedBytes || zRec.size !== expectedBytes) {
      throw new Error('Unexpected coordinate block size in DCD frame');
    }
    frames.push({
      x: readFloat32Array(view, xRec.start, natoms, littleEndian),
      y: readFloat32Array(view, yRec.start, natoms, littleEndian),
      z: readFloat32Array(view, zRec.start, natoms, littleEndian),
    });
  }

  // Keep all parsed frames. Some producers write inconsistent NSET values.
  return { natoms, frames };
}

export function extractPaeFromJSON(paeJson: any): number[][] | null {
  if (!paeJson) return null;
  if (paeJson.pae && Array.isArray(paeJson.pae)) return paeJson.pae;
  if (paeJson.predicted_aligned_error && Array.isArray(paeJson.predicted_aligned_error)) return paeJson.predicted_aligned_error;
  if (Array.isArray(paeJson) && paeJson.length > 0 && paeJson[0].predicted_aligned_error) return paeJson[0].predicted_aligned_error;
  console.warn('Could not find PAE matrix in JSON.');
  return null;
}

export function cleanObjectName(name: string): string { return name.replace(/\.(cif|pdb|ent|zip)$/i, ''); }


