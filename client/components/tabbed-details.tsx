"use client"

import type React from "react"
import { useState, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import type { Components } from "react-markdown"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import type { ContractData } from "@/lib/types"
import { FileText, Target, Lightbulb } from "lucide-react"
import { contractStorage } from "@/lib/localStorage"
import { useLocalStorage } from "@/lib/useLocalStorage"

interface TabbedDetailsProps {
    data: ContractData
}

const tabConfig = [
    {
        id: "analysis",
        label: "Analysis",
        icon: FileText,
        description: "Detailed contract analysis"
    },
    {
        id: "keyPoints",
        label: "Key Points",
        icon: Target,
        description: "Important contract highlights"
    },
    {
        id: "recommendations",
        label: "Recommendations",
        icon: Lightbulb,
        description: "Strategic recommendations"
    }
]

// Simple table parser that creates React components directly
const parseAndRenderContent = (content: string) => {
    const lines = content.split('\n')
    const elements: React.ReactNode[] = []
    let i = 0

    while (i < lines.length) {
        const line = lines[i].trim()

        // Check if this looks like a table header
        if (line.includes('|') && line.split('|').length > 2) {
            const nextLine = lines[i + 1]?.trim()

            // Check if next line is a separator (contains dashes)
            if (nextLine && nextLine.includes('-') && nextLine.includes('|')) {
                // This is a table - parse it
                const tableLines = [line]
                i += 2 // Skip separator line

                // Collect table rows
                while (i < lines.length && lines[i].trim().includes('|')) {
                    tableLines.push(lines[i].trim())
                    i++
                }

                // Create React table component
                elements.push(
                    <TableComponent key={`table-${elements.length}`} lines={tableLines} />
                )
                continue
            }
        }

        // If not a table, collect consecutive non-table lines for markdown
        const markdownLines = []
        while (i < lines.length &&
        (!lines[i].includes('|') ||
            !lines[i + 1]?.includes('-'))) {
            markdownLines.push(lines[i])
            i++
        }

        if (markdownLines.length > 0) {
            elements.push(
                <ReactMarkdown
                    key={`markdown-${elements.length}`}
                    components={{
                        h1: ({ children }) => (
                            <h1 className="text-2xl font-bold text-gray-900 mb-4 mt-6 first:mt-0 pb-2 border-b border-gray-200">
                                {children}
                            </h1>
                        ),
                        h2: ({ children }) => (
                            <h2 className="text-xl font-semibold text-gray-900 mb-3 mt-5 first:mt-0">
                                {children}
                            </h2>
                        ),
                        h3: ({ children }) => (
                            <h3 className="text-lg font-semibold text-gray-900 mb-2 mt-4 first:mt-0">
                                {children}
                            </h3>
                        ),
                        p: ({ children }) => (
                            <p className="mb-4 leading-relaxed text-gray-700">
                                {children}
                            </p>
                        ),
                        ul: ({ children }) => (
                            <ul className="space-y-2 mb-4">
                                {children}
                            </ul>
                        ),
                        ol: ({ children }) => (
                            <ol className="space-y-2 mb-4 list-decimal list-inside">
                                {children}
                            </ol>
                        ),
                        li: ({ children }) => (
                            <li className="flex items-start gap-2 text-gray-700">
                                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full mt-2 flex-shrink-0"></span>
                                <span className="flex-1">{children}</span>
                            </li>
                        ),
                        blockquote: ({ children }) => (
                            <blockquote className="border-l-4 border-indigo-300 bg-indigo-50 pl-4 py-3 my-4 text-gray-700 italic rounded-r-md">
                                {children}
                            </blockquote>
                        ),
                        strong: ({ children }) => (
                            <strong className="font-semibold text-gray-900">
                                {children}
                            </strong>
                        ),
                        em: ({ children }) => (
                            <em className="italic text-gray-700">
                                {children}
                            </em>
                        ),
                        code: ({ children }) => (
                            <code className="bg-gray-100 text-indigo-700 px-1.5 py-0.5 rounded text-sm font-mono border">
                                {children}
                            </code>
                        ),
                        pre: ({ children }) => (
                            <pre className="bg-gray-100 text-gray-800 p-4 rounded-md text-sm font-mono overflow-x-auto border mb-4">
                                {children}
                            </pre>
                        )
                    }}
                >
                    {markdownLines.join('\n')}
                </ReactMarkdown>
            )
        }
    }

    return elements
}

// Table component to render tables properly
const TableComponent: React.FC<{ lines: string[] }> = ({ lines }) => {
    const [headerLine, ...dataLines] = lines

    // Parse header
    const headers = headerLine.split('|')
        .map(h => h.trim())
        .filter(h => h)

    // Parse data rows
    const rows = dataLines.map(line =>
        line.split('|')
            .map(cell => cell.trim())
            .filter(cell => cell)
    )

    return (
        <div className="overflow-x-auto mb-6 rounded-lg border border-gray-200">
            <table className="w-full border-collapse bg-white">
                <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                    {headers.map((header, idx) => (
                        <th key={idx} className="px-6 py-3 text-left font-semibold text-gray-900 text-sm uppercase tracking-wider">
                            {header}
                        </th>
                    ))}
                </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                {rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-gray-50 transition-colors">
                        {row.map((cell, cellIdx) => (
                            <td key={cellIdx} className="px-6 py-4 text-gray-700 text-sm">
                                <div className="max-w-xs lg:max-w-none whitespace-normal">
                                    {cell}
                                </div>
                            </td>
                        ))}
                    </tr>
                ))}
                </tbody>
            </table>
        </div>
    )
}

export function TabbedDetails({ data }: TabbedDetailsProps) {
    // Use the localStorage utilities and hooks
    const [activeTab, setActiveTab] = useLocalStorage('contract-active-tab', 'analysis')
    const [persistedData, setPersistedData] = useState<ContractData>(() => {
        return contractStorage.getContractData() || data
    })
    const [isDataFromStorage, setIsDataFromStorage] = useState(false)

    // Check if there's stored data on mount
    useEffect(() => {
        const storedData = contractStorage.getContractData()
        if (storedData) {
            setIsDataFromStorage(true)
        }
    }, [])

    // Persist contract data when it changes (but only if it's new data)
    useEffect(() => {
        if (data && JSON.stringify(data) !== JSON.stringify(persistedData)) {
            contractStorage.setContractData(data)
            setPersistedData(data)
            setIsDataFromStorage(false)
        }
    }, [data, persistedData])

    const getTabContent = (tabId: string) => {
        switch (tabId) {
            case "analysis":
                return persistedData.analysis
            case "keyPoints":
                return persistedData.keyPoints
            case "recommendations":
                return persistedData.recommendations
            default:
                return ""
        }
    }

    const activeTabConfig = tabConfig.find(tab => tab.id === activeTab)

    const handleClearStorage = () => {
        contractStorage.clearContractData()
        setActiveTab('analysis')
        setPersistedData(data)
        setIsDataFromStorage(false)
    }

    return (
        <Card className="h-full shadow-lg bg-white border-0 overflow-hidden">
            <CardHeader className="pb-0">
                <div className="border-b border-gray-200">
                    <div className="flex overflow-x-auto scrollbar-hide">
                        {tabConfig.map((tab) => (
                            <TabButton
                                key={tab.id}
                                isActive={activeTab === tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                icon={tab.icon}
                                label={tab.label}
                                description={tab.description}
                            />
                        ))}
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-0 h-full">
                <div className="h-full overflow-y-auto">
                    <div className="p-6">
                        {/* Data persistence indicator */}
                        {isDataFromStorage && (
                            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                                <div className="flex items-center gap-2 text-sm text-blue-800">
                                    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                    </svg>
                                    Displaying previously stored analysis
                                </div>
                            </div>
                        )}

                        {/* Tab Header with Icon and Description */}
                        <div className="mb-6 pb-4 border-b border-gray-100">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-3">
                                    {activeTabConfig?.icon && (
                                        <activeTabConfig.icon className="h-5 w-5 text-indigo-600" />
                                    )}
                                    <h2 className="text-xl font-semibold text-gray-900">
                                        {activeTabConfig?.label}
                                    </h2>
                                </div>
                                <button
                                    onClick={handleClearStorage}
                                    className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200 hover:border-gray-300 transition-colors"
                                    title="Clear stored data and reset to current analysis"
                                >
                                    Clear Storage
                                </button>
                            </div>
                            <p className="text-sm text-gray-600">
                                {activeTabConfig?.description}
                            </p>
                        </div>

                        {/* Content with custom table rendering */}
                        <div className="markdown-content">
                            {parseAndRenderContent(getTabContent(activeTab))}
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

interface TabButtonProps {
    isActive: boolean
    onClick: () => void
    icon: React.ElementType
    label: string
    description: string
}

function TabButton({ isActive, onClick, icon: Icon, label, description }: TabButtonProps) {
    return (
        <button
            className={`group relative px-6 py-4 text-sm font-medium border-b-2 transition-all duration-200 min-w-[140px] whitespace-nowrap ${
                isActive
                    ? "border-indigo-600 text-indigo-600 bg-indigo-50/50"
                    : "border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300 hover:bg-gray-50/50"
            }`}
            onClick={onClick}
            title={description}
        >
            <div className="flex items-center gap-2 justify-center">
                <Icon
                    className={`h-4 w-4 transition-colors ${
                        isActive ? "text-indigo-600" : "text-gray-400 group-hover:text-gray-600"
                    }`}
                />
                <span>{label}</span>
            </div>

            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-md opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pointer-events-none whitespace-nowrap z-10">
                {description}
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
            </div>
        </button>
    )
}