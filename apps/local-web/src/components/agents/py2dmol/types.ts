export type Vec3 = [number, number, number];
export type Mat3 = [Vec3, Vec3, Vec3];

export interface Atom {
  record: string;
  atomName: string;
  resName: string;
  chain: string;
  resSeq: number;
  x: number;
  y: number;
  z: number;
  b: number;
  element: string;
  lchain?: string;
  authChain?: string;
}

export interface FrameData {
  coords: number[][];
  plddts: number[];
  chains: string[];
  atom_types: string[];
  position_names?: string[];
  residue_numbers?: number[];
  pae?: number[][] | null;
}


