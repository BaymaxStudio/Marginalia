import { create } from 'zustand'

export const useReaderStore = create((set, get) => ({
  documents: [],
  currentDocument: null,
  currentChapter: null,
  vocabulary: [],
  settings: null,

  setDocuments: (docs) => set({ documents: docs }),
  setCurrentDocument: (doc) => set({ currentDocument: doc }),
  setCurrentChapter: (ch) => set({ currentChapter: ch }),
  setVocabulary: (words) => set({ vocabulary: words }),
  setSettings: (s) => set({ settings: s }),

  removeDocument: (id) => set((s) => ({
    documents: s.documents.filter((d) => d.id !== id),
  })),
}))
