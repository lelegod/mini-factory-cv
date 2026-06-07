export interface TagImage {
  tag_id: number;
  defect_type?: string;
  image_base64: string;
  timestamp: string;
}

export interface State {
  approved_count: number;
  defective_count: number;
  approved_images: TagImage[];
  defective_images: TagImage[];
  camera_image: string | null;
  last_scan: string | null;
}

const globalState = global as typeof global & { __factory_state?: State };

if (!globalState.__factory_state) {
  globalState.__factory_state = {
    approved_count: 0,
    defective_count: 0,
    approved_images: [],
    defective_images: [],
    camera_image: null,
    last_scan: null,
  };
}

export const state = globalState.__factory_state;

export function setState(payload: {
  approved_count: number;
  defective_count: number;
  approved_images: TagImage[];
  defective_images: TagImage[];
  camera_image_base64: string;
}) {
  state.approved_count = payload.approved_count;
  state.defective_count = payload.defective_count;
  state.approved_images = payload.approved_images;
  state.defective_images = payload.defective_images;
  state.camera_image = payload.camera_image_base64;
  state.last_scan = new Date().toISOString();
}
