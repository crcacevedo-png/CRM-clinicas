import { Component } from 'react';

/**
 * Root error boundary — catches uncaught errors in the React tree so a single
 * broken component doesn't take down the whole app with a blank screen.
 */
export default class ErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info?.componentStack);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/';
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6" data-testid="error-boundary">
        <div className="max-w-md w-full bg-white rounded-xl shadow-sm border border-slate-200 p-8 text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-rose-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M5.07 19h13.86a2 2 0 001.74-2.97L13.74 4.04a2 2 0 00-3.48 0L3.32 16.03A2 2 0 005.07 19z" />
            </svg>
          </div>
          <h1 className="text-lg font-semibold text-slate-900 mb-2">Algo salió mal</h1>
          <p className="text-sm text-slate-500 mb-6">
            Encontramos un error inesperado al renderizar la pantalla. Tu información está segura.
            Por favor recarga la página; si el problema persiste, contacta soporte.
          </p>
          <button
            onClick={this.handleReload}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium rounded-lg transition-colors"
            data-testid="error-reload-btn"
          >
            Volver al inicio
          </button>
          {process.env.NODE_ENV !== 'production' && this.state.error && (
            <details className="mt-6 text-left text-xs text-slate-500">
              <summary className="cursor-pointer">Detalles (solo desarrollo)</summary>
              <pre className="mt-2 p-3 bg-slate-50 rounded overflow-x-auto">
                {String(this.state.error?.stack || this.state.error)}
              </pre>
            </details>
          )}
        </div>
      </div>
    );
  }
}
