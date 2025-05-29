"use client"

import { useState, useEffect } from "react"
import { UploadCard } from "./upload-card"
// import { RiskScoreCard } from "./risk-score-card"
import { TabbedDetails } from "./tabbed-details"
import { ProjectHeader } from "./project-header"
import { ApiConfigComponent } from "./api-config"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import type { ContractData, ApiConfig, AnalysisType } from "@/lib/types"
import { apiService } from "@/lib/api-service"
import { contractStorage } from "@/lib/localStorage"
import { useLocalStorage } from "@/lib/useLocalStorage"

export function ContractDashboard() {
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [contractData, setContractData] = useState<ContractData | null>(null)
  const [isLoadingFromStorage, setIsLoadingFromStorage] = useState(true)

  // Use localStorage utilities for all persistent state
  const [isUploadMinimized, setIsUploadMinimized] = useLocalStorage('upload-minimized', false)
  const [apiConfig, setApiConfig] = useLocalStorage<ApiConfig | null>('api-config', null)
  const [analysisType, setAnalysisType] = useLocalStorage<AnalysisType>('analysis-type', { type: "Contract Review" })
  const [customQuery, setCustomQuery] = useLocalStorage('custom-query', '')

  // Load persisted data on component mount
  useEffect(() => {
    const loadPersistedData = () => {
      try {
        // Load contract data
        const storedContractData = contractStorage.getContractData()
        if (storedContractData) {
          setContractData(storedContractData)
          setIsUploadMinimized(true) // Minimize upload card if we have data
        }

        // Set API config in service if it exists
        if (apiConfig) {
          apiService.setConfig(apiConfig)
        }
      } catch (error) {
        console.warn('Error loading persisted data:', error)
      } finally {
        setIsLoadingFromStorage(false)
      }
    }

    loadPersistedData()
  }, [apiConfig])

  // Set API config in service when it changes
  useEffect(() => {
    if (apiConfig) {
      apiService.setConfig(apiConfig)
    }
  }, [apiConfig])

  const handleApiConfigChange = (config: ApiConfig) => {
    setApiConfig(config)
  }

  const handleFileUpload = async (file: File) => {
    if (!apiConfig) {
      alert("Please configure API settings first")
      return
    }

    setIsAnalyzing(true)
    setIsUploadMinimized(true)

    try {
      const analysis: AnalysisType = analysisType.type === "Custom Query"
          ? { ...analysisType, customQuery }
          : analysisType

      const data = await apiService.uploadAndAnalyze(file, analysis)
      setContractData(data)

      // Persist the new contract data immediately
      contractStorage.setContractData(data)
    } catch (error) {
      console.error("Analysis failed:", error)
      alert("Analysis failed. Please check your API configuration and try again.")
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleNewUpload = () => {
    setContractData(null)
    setIsUploadMinimized(false)
    setIsAnalyzing(false)

    // Clear persisted contract data but keep other settings
    contractStorage.clearContractData()
  }

  const handleClearAllData = () => {
    setContractData(null)
    setApiConfig(null)
    setAnalysisType({ type: "Contract Review" })
    setCustomQuery("")
    setIsUploadMinimized(false)

    // Clear all persisted data
    contractStorage.clearAll()
  }

  // Show loading state while checking for persisted data
  if (isLoadingFromStorage) {
    return (
        <div className="min-h-screen bg-white flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading...</p>
          </div>
        </div>
    )
  }

  return (
      <div className="min-h-screen bg-white">
        <ProjectHeader />

        <div className="container mx-auto px-4 py-8 max-w-7xl">
          {/* Show data persistence indicator if we have stored data */}
          {contractData && contractStorage.getContractData() && (
              <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                    </svg>
                    <span className="text-blue-800 font-medium">
                    Previous analysis restored from storage
                  </span>
                  </div>
                  <button
                      onClick={handleClearAllData}
                      className="text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    Clear All Data
                  </button>
                </div>
              </div>
          )}

          {!apiConfig && (
              <ApiConfigComponent onConfigChange={handleApiConfigChange} />
          )}

          <div className="mb-6 space-y-4">
            <div>
              <Label htmlFor="analysis-type">Select Analysis Type</Label>
              <Select
                  value={analysisType.type}
                  onValueChange={(value) => setAnalysisType({ type: value as AnalysisType["type"] })}
              >
                <SelectTrigger id="analysis-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Contract Review">Contract Review</SelectItem>
                  <SelectItem value="Legal Research">Legal Research</SelectItem>
                  <SelectItem value="Risk Assessment">Risk Assessment</SelectItem>
                  <SelectItem value="Custom Query">Custom Query</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {analysisType.type === "Custom Query" && (
                <div>
                  <Label htmlFor="custom-query">Custom Query</Label>
                  <Textarea
                      id="custom-query"
                      value={customQuery}
                      onChange={(e) => setCustomQuery(e.target.value)}
                      placeholder="Enter your specific legal analysis query..."
                      rows={3}
                  />
                </div>
            )}
          </div>

          <div className={`transition-all duration-300 ${isUploadMinimized ? "mb-4" : "mb-8"}`}>
            <UploadCard
                onFileUpload={handleFileUpload}
                isAnalyzing={isAnalyzing}
                isMinimized={isUploadMinimized}
                onNewUpload={handleNewUpload}
                hasContract={!!contractData}
            />
          </div>

          {contractData && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/*<div className="lg:col-span-1">*/}
                {/*  <RiskScoreCard data={contractData} />*/}
                {/*</div>*/}
                <div className="lg:col-span-2">
                  <TabbedDetails data={contractData} />
                </div>
              </div>
          )}
        </div>
      </div>
  )
}