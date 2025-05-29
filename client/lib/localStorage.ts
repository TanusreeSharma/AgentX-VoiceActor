/**
 * Safe localStorage wrapper that handles SSR and errors gracefully
 */
export const safeLocalStorage = {
    /**
     * Get an item from localStorage safely
     */
    getItem: (key: string): string | null => {
        if (typeof window === 'undefined') return null

        try {
            return localStorage.getItem(key)
        } catch (error) {
            console.warn(`localStorage.getItem failed for key "${key}":`, error)
            return null
        }
    },

    /**
     * Set an item in localStorage safely
     */
    setItem: (key: string, value: string): boolean => {
        if (typeof window === 'undefined') return false

        try {
            localStorage.setItem(key, value)
            return true
        } catch (error) {
            console.warn(`localStorage.setItem failed for key "${key}":`, error)
            return false
        }
    },

    /**
     * Remove an item from localStorage safely
     */
    removeItem: (key: string): boolean => {
        if (typeof window === 'undefined') return false

        try {
            localStorage.removeItem(key)
            return true
        } catch (error) {
            console.warn(`localStorage.removeItem failed for key "${key}":`, error)
            return false
        }
    },

    /**
     * Check if localStorage is available
     */
    isAvailable: (): boolean => {
        if (typeof window === 'undefined') return false

        try {
            const testKey = '__localStorage_test__'
            localStorage.setItem(testKey, 'test')
            localStorage.removeItem(testKey)
            return true
        } catch {
            return false
        }
    },

    /**
     * Clear all localStorage data
     */
    clear: (): boolean => {
        if (typeof window === 'undefined') return false

        try {
            localStorage.clear()
            return true
        } catch (error) {
            console.warn('localStorage.clear failed:', error)
            return false
        }
    }
}

/**
 * Get and parse JSON from localStorage with type safety
 */
export const getStoredJSON = <T>(key: string, fallback: T): T => {
    const stored = safeLocalStorage.getItem(key)
    if (!stored) return fallback

    try {
        return JSON.parse(stored) as T
    } catch (error) {
        console.warn(`Failed to parse JSON for key "${key}":`, error)
        return fallback
    }
}

/**
 * Set JSON data to localStorage with type safety
 */
export const setStoredJSON = <T>(key: string, value: T): boolean => {
    try {
        return safeLocalStorage.setItem(key, JSON.stringify(value))
    } catch (error) {
        console.warn(`Failed to stringify JSON for key "${key}":`, error)
        return false
    }
}

/**
 * Storage keys used throughout the application
 * This helps prevent typos and makes it easy to update keys
 */
export const STORAGE_KEYS = {
    // Contract Dashboard
    CONTRACT_DATA: 'contract-data',
    CONTRACT_ACTIVE_TAB: 'contract-active-tab',
    API_CONFIG: 'api-config',
    ANALYSIS_TYPE: 'analysis-type',
    CUSTOM_QUERY: 'custom-query',

    // User Preferences
    THEME: 'app-theme',
    LANGUAGE: 'app-language',

    // UI State
    SIDEBAR_COLLAPSED: 'sidebar-collapsed',
    UPLOAD_MINIMIZED: 'upload-minimized',

    // Recent Activity
    RECENT_UPLOADS: 'recent-uploads',
    RECENT_ANALYSES: 'recent-analyses',
} as const

/**
 * Type-safe storage operations for specific data types
 */
export const contractStorage = {
    getContractData: () => getStoredJSON(STORAGE_KEYS.CONTRACT_DATA, null),
    setContractData: (data: any) => setStoredJSON(STORAGE_KEYS.CONTRACT_DATA, data),
    clearContractData: () => safeLocalStorage.removeItem(STORAGE_KEYS.CONTRACT_DATA),

    getActiveTab: () => safeLocalStorage.getItem(STORAGE_KEYS.CONTRACT_ACTIVE_TAB) || 'analysis',
    setActiveTab: (tab: string) => safeLocalStorage.setItem(STORAGE_KEYS.CONTRACT_ACTIVE_TAB, tab),

    getApiConfig: () => getStoredJSON(STORAGE_KEYS.API_CONFIG, null),
    setApiConfig: (config: any) => setStoredJSON(STORAGE_KEYS.API_CONFIG, config),
    clearApiConfig: () => safeLocalStorage.removeItem(STORAGE_KEYS.API_CONFIG),

    getAnalysisType: () => getStoredJSON(STORAGE_KEYS.ANALYSIS_TYPE, {type: 'Contract Review'}),
    setAnalysisType: (type: any) => setStoredJSON(STORAGE_KEYS.ANALYSIS_TYPE, type),

    getCustomQuery: () => safeLocalStorage.getItem(STORAGE_KEYS.CUSTOM_QUERY) || '',
    setCustomQuery: (query: string) => safeLocalStorage.setItem(STORAGE_KEYS.CUSTOM_QUERY, query),

    // Clear all contract-related data
    clearAll: () => {
        safeLocalStorage.removeItem(STORAGE_KEYS.CONTRACT_DATA)
        safeLocalStorage.removeItem(STORAGE_KEYS.CONTRACT_ACTIVE_TAB)
        safeLocalStorage.removeItem(STORAGE_KEYS.API_CONFIG)
        safeLocalStorage.removeItem(STORAGE_KEYS.ANALYSIS_TYPE)
        safeLocalStorage.removeItem(STORAGE_KEYS.CUSTOM_QUERY)
    }
}

/**
 * Generic storage manager for any data type
 */
export class StorageManager<T> {
    constructor(private key: string, private defaultValue: T) {
    }

    get(): T {
        return getStoredJSON(this.key, this.defaultValue)
    }

    set(value: T): boolean {
        return setStoredJSON(this.key, value)
    }

    remove(): boolean {
        return safeLocalStorage.removeItem(this.key)
    }

    exists(): boolean {
        return safeLocalStorage.getItem(this.key) !== null
    }
}