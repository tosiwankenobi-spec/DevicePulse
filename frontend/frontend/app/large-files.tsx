import React from 'react';
import { ProtectedStorageGuide } from '@/src/components/ProtectedStorageGuide';

export default function LargeFiles() {
  return (
    <ProtectedStorageGuide
      title="Large Files"
      icon="folder-open-outline"
      description="Find large files using Android Storage"
      guidance="Android's storage manager can inspect the real videos, downloads and documents on this phone while keeping deletion under your control."
    />
  );
}
