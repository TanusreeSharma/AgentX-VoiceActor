import { useState, useEffect, useCallback } from 'react'
import { safeLocalStorage, getStoredJSON, setStoredJSON } from './localStorage'

/**
 * Hook for managing localStorage with React state synchronization
 */
export function useLocalStorage<T>(
    key: string,
    initialValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
    // Initialize state with value from localStorage or initial value
    const [storedValue, setStoredValue] = useState<T>(() => {
        return getStoredJSON(key, initialValue)
    })

    // Return a wrapped version of useState's setter function that persists the new value to localStorage
    const setValue = useCallback((value: T | ((prev: T) => T)) => {
        try {
            // Allow value to be a function so we have the same API as useState
            const valueToStore = value instanceof Function ? value(storedValue) : value

            // Save state
            setStoredValue(valueToStore)

            // Save to localStorage
            setStoredJSON(key, valueToStore)
        } catch (error) {
            console.error(`Error setting localStorage key "${key}":`, error)
        }
    }, [key, storedValue])

    // Function to remove the item from localStorage
    const removeValue = useCallback(() => {
        try {
            setStoredValue(initialValue)
            safeLocalStorage.removeItem(key)
        } catch (error) {
            console.error(`Error removing localStorage key "${key}":`, error)
        }
    }, [key, initialValue])

    return [storedValue, setValue, removeValue]
}

/**
 * Hook for managing localStorage with automatic synchronization across tabs
 */
export function useLocalStorageSync<T>(
    key: string,
    initialValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
    const [storedValue, setValue, removeValue] = useLocalStorage(key, initialValue)

    // Listen for storage changes from other tabs
    useEffect(() => {
        const handleStorageChange = (e: StorageEvent) => {
            if (e.key === key && e.newValue !== null) {
                try {
                    const newValue = JSON.parse(e.newValue)
                    setValue(newValue)
                } catch (error) {
                    console.error(`Error parsing storage event for key "${key}":`, error)
                }
            }
        }

        window.addEventListener('storage', handleStorageChange)
        return () => window.removeEventListener('storage', handleStorageChange)
    }, [key, setValue])

    return [storedValue, setValue, removeValue]
}

/**
 * Hook for managing boolean localStorage values
 */
export function useLocalStorageBoolean(
    key: string,
    initialValue: boolean = false
): [boolean, () => void, () => void, (value: boolean) => void] {
    const [value, setValue, removeValue] = useLocalStorage(key, initialValue)

    const toggle = useCallback(() => {
        setValue(prev => !prev)
    }, [setValue])

    const setTrue = useCallback(() => {
        setValue(true)
    }, [setValue])

    const setFalse = useCallback(() => {
        setValue(false)
    }, [setValue])

    const setBoolean = useCallback((newValue: boolean) => {
        setValue(newValue)
    }, [setValue])

    return [value, toggle, removeValue, setBoolean]
}

/**
 * Hook for managing array localStorage values with helper methods
 */
export function useLocalStorageArray<T>(
    key: string,
    initialValue: T[] = []
): [
    T[],
    {
        add: (item: T) => void
        remove: (index: number) => void
        update: (index: number, item: T) => void
        clear: () => void
        set: (items: T[]) => void
    }
] {
    const [array, setArray, removeValue] = useLocalStorage<T[]>(key, initialValue)

    const add = useCallback((item: T) => {
        setArray(prev => [...prev, item])
    }, [setArray])

    const remove = useCallback((index: number) => {
        setArray(prev => prev.filter((_, i) => i !== index))
    }, [setArray])

    const update = useCallback((index: number, item: T) => {
        setArray(prev => prev.map((existing, i) => i === index ? item : existing))
    }, [setArray])

    const clear = useCallback(() => {
        setArray([])
    }, [setArray])

    const set = useCallback((items: T[]) => {
        setArray(items)
    }, [setArray])

    return [
        array,
        { add, remove, update, clear, set }
    ]
}

/**
 * Hook for detecting localStorage availability
 */
export function useLocalStorageAvailable(): boolean {
    const [isAvailable, setIsAvailable] = useState(false)

    useEffect(() => {
        setIsAvailable(safeLocalStorage.isAvailable())
    }, [])

    return isAvailable
}