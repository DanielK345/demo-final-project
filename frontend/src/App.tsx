import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import CustomerUI from './components/CustomerUI';
import OperatorUI from './components/OperatorUI';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={
          <div className="min-h-screen flex flex-col items-center justify-center bg-surface-container-low font-body-md gap-6">
            <h1 className="font-headline-lg text-primary mb-4">AloSM AI Booking MVP</h1>
            <div className="flex gap-4">
              <Link to="/customer" className="px-6 py-3 bg-primary text-white rounded-lg font-label-lg hover:bg-tertiary transition-colors">
                Giao diện Khách Hàng
              </Link>
              <Link to="/operator" className="px-6 py-3 bg-white text-primary border border-primary rounded-lg font-label-lg hover:bg-surface transition-colors">
                Giao diện Tổng Đài Viên
              </Link>
            </div>
          </div>
        } />
        <Route path="/customer" element={<CustomerUI />} />
        <Route path="/operator" element={<OperatorUI />} />
      </Routes>
    </Router>
  );
}

export default App;
