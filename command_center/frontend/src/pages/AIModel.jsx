import FeatureImportance from '../components/ai/FeatureImportance'
import Predictions from '../components/ai/Predictions'
import ModelMetrics from '../components/ai/ModelMetrics'

export default function AIModel() {
  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">AI / Model</h2>
        <p className="text-sm text-gray-500">Model performance and predictions</p>
      </div>

      <ModelMetrics />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <FeatureImportance />
        <Predictions />
      </div>
    </div>
  )
}
