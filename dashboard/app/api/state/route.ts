import { NextResponse } from "next/server";
import { state } from "@/lib/state";

export async function GET() {
  return NextResponse.json(state);
}
