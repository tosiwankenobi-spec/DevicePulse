import React from 'react';
import { ProtectedStorageGuide } from '@/src/components/ProtectedStorageGuide';

export default function Duplicates() {
  return (
    <ProtectedStorageGuide
      title="Duplicate Photos"
      icon="copy-outline"
      description="Review possible duplicates with Android"
      guidance="DevicePulse does not invent photo matches or delete images silently. Use Android Storage or your trusted photo manager to compare real files before removing them."
    />
  );
}
