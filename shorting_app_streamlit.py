import streamlit as st
import pandas as pd
import os
from datetime import datetime
from prediction_tracker import PredictionTracker

# Page configuration
st.set_page_config(
    page_title="Short-Selling Recommendations",
    page_icon="📉",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .scenario-card {
        padding: 1.5rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 5px solid;
    }
    .bullish {
        background: #d4edda;
        border-color: #28a745;
    }
    .bearish {
        background: #f8d7da;
        border-color: #dc3545;
    }
    .neutral {
        background: #fff3cd;
        border-color: #ffc107;
    }
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffc107;
        padding: 1rem;
        border-radius: 10px;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📉 Short-Selling Recommendation System</h1>
    <p>NSE Options & Futures Analysis</p>
</div>
""", unsafe_allow_html=True)

# Initialize tracker
tracker = PredictionTracker()

# Add tabs for different functions
tab1, tab2, tab3 = st.tabs(["📊 Analysis", "📈 Performance", "🔧 Verify Predictions"])

with tab1:
    # File upload section
    st.markdown("## 📁 Upload NSE Data Files")
    st.info("Upload your daily NSE data files to generate recommendations. Required files:")
    st.markdown("""
    - Spurts-in-OI-Rise-in-OI-and-Slide-in-Price-[date].csv
    - Spurts-in-OI-Slide-in-OI-and-Slide-in-Price-[date].csv
    """)

    uploaded_files = st.file_uploader(
        "Upload CSV files",
        type=['csv'],
        accept_multiple_files=True,
        help="Upload the NSE data CSV files"
    )

    # Function to process data
    def get_recommendations(uploaded_files):
        recommendations = {}
        
        for file in uploaded_files:
            try:
                df = pd.read_csv(file)
                filename = file.name.lower()
                
                # Scenario 1: Rise in OI + Slide in Price
                if 'rise' in filename and 'slide' in filename and 'price' in filename:
                    stock_futures = df[df['Instrument'] == 'Stock Futures'].copy()
                    
                    for _, row in stock_futures.iterrows():
                        try:
                            symbol = row['Symbol']
                            oi_change_pct = float(str(row['%chng<br/>in OI']).replace('%', '').replace(',', ''))
                            price_change_pct = float(str(row['% CHNG in LTP']).replace('%', '').replace(',', ''))
                            underlying = row['Underlying value']
                            
                            # Get current model weights
                            weights = tracker.get_model_weights('RISE_OI_SLIDE_PRICE')
                            if weights:
                                oi_weight = weights['oi_weight']
                                price_weight = weights['price_weight']
                            else:
                                oi_weight = 0.6
                                price_weight = 0.4
                            
                            bearish_score = (oi_change_pct * oi_weight) + (abs(price_change_pct) * price_weight)
                            
                            if symbol not in recommendations:
                                recommendations[symbol] = {
                                    'symbol': symbol,
                                    'underlying_price': underlying,
                                    'bearish_score': 0,
                                    'signal_type': '',
                                    'oi_change': 0,
                                    'price_change': 0,
                                    'volume': 0
                                }
                            
                            if bearish_score > recommendations[symbol]['bearish_score']:
                                recommendations[symbol]['bearish_score'] = bearish_score
                                recommendations[symbol]['signal_type'] = 'RISE_OI_SLIDE_PRICE'
                                recommendations[symbol]['oi_change'] = oi_change_pct
                                recommendations[symbol]['price_change'] = price_change_pct
                                recommendations[symbol]['volume'] = row['Volume']
                        except:
                            continue
                
                # Scenario 2: Slide in OI + Slide in Price
                elif 'slide' in filename and 'price' in filename and 'rise' not in filename:
                    stock_futures = df[df['Instrument'] == 'Stock Futures'].copy()
                    
                    for _, row in stock_futures.iterrows():
                        try:
                            symbol = row['Symbol']
                            oi_change_pct = float(str(row['%chng<br/>in OI']).replace('%', '').replace(',', ''))
                            price_change_pct = float(str(row['% CHNG in LTP']).replace('%', '').replace(',', ''))
                            underlying = row['Underlying value']
                            
                            # Get current model weights
                            weights = tracker.get_model_weights('SLIDE_OI_SLIDE_PRICE')
                            if weights:
                                oi_weight = weights['oi_weight']
                                price_weight = weights['price_weight']
                            else:
                                oi_weight = 0.5
                                price_weight = 0.5
                            
                            bearish_score = (abs(oi_change_pct) * oi_weight) + (abs(price_change_pct) * price_weight)
                            
                            if symbol not in recommendations:
                                recommendations[symbol] = {
                                    'symbol': symbol,
                                    'underlying_price': underlying,
                                    'bearish_score': 0,
                                    'signal_type': '',
                                    'oi_change': 0,
                                    'price_change': 0,
                                    'volume': 0
                                }
                            
                            if bearish_score > recommendations[symbol]['bearish_score']:
                                recommendations[symbol]['bearish_score'] = bearish_score
                                recommendations[symbol]['signal_type'] = 'SLIDE_OI_SLIDE_PRICE'
                                recommendations[symbol]['oi_change'] = oi_change_pct
                                recommendations[symbol]['price_change'] = price_change_pct
                                recommendations[symbol]['volume'] = row['Volume']
                        except:
                            continue
            except:
                continue
        
        # Convert to DataFrame and sort
        if recommendations:
            rec_df = pd.DataFrame(list(recommendations.values()))
            rec_df = rec_df.sort_values('bearish_score', ascending=False)
            
            # Calculate probability
            max_score = rec_df['bearish_score'].max()
            if max_score > 0:
                rec_df['probability'] = (rec_df['bearish_score'] / max_score) * 100
            else:
                rec_df['probability'] = 0
            
            return rec_df.head(10)
        else:
            return pd.DataFrame()

    # OI Explanation Section
    st.markdown("## 📊 Understanding OI (Open Interest)")

    with st.expander("What is Open Interest?", expanded=True):
        st.markdown("""
        **Open Interest (OI)** represents the total number of outstanding derivative contracts (options/futures) that have not been settled.
        
        - **Rising OI:** New money entering the market - new positions being created
        - **Falling OI:** Money exiting the market - positions being closed
        """)

    st.markdown("### The 4 OI + Price Scenarios")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="scenario-card bullish">
            <h4>📈 RISE OI + RISE Price</h4>
            <p><strong>Strong bullish</strong> - Fresh long positions being created</p>
            <p>⚠️ <strong>AVOID for shorting</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="scenario-card bearish">
            <h4>📉 RISE OI + SLIDE Price</h4>
            <p><strong>Bearish</strong> - Longs trapped, shorts building</p>
            <p>✅ <strong>BEST for shorting</strong></p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="scenario-card neutral">
            <h4>🔄 SLIDE OI + RISE Price</h4>
            <p><strong>Short covering</strong> - Bulls returning</p>
            <p>⚠️ <strong>AVOID for shorting</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="scenario-card bearish">
            <h4>📉 SLIDE OI + SLIDE Price</h4>
            <p><strong>Long unwinding</strong> - Panic selling</p>
            <p>✅ <strong>GOOD for shorting</strong></p>
        </div>
        """, unsafe_allow_html=True)

    # Process and display recommendations
    if uploaded_files:
        st.markdown("---")
        st.markdown("## 🎯 Top Short-Selling Recommendations")
        
        with st.spinner("Analyzing data..."):
            recommendations_df = get_recommendations(uploaded_files)
        
        if not recommendations_df.empty:
            # Save predictions to database
            today = datetime.now().strftime("%Y-%m-%d")
            for _, row in recommendations_df.iterrows():
                tracker.save_prediction(
                    date=today,
                    symbol=row['symbol'],
                    signal_type=row['signal_type'],
                    oi_change=row['oi_change'],
                    price_change=row['price_change'],
                    predicted_probability=row['probability'],
                    actual_price=row['underlying_price']
                )
            
            st.success(f"✅ Predictions saved to database for {today}")
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Stocks Analyzed", len(recommendations_df))
            col2.metric("Strong Signals", len(recommendations_df[recommendations_df['signal_type'] == 'RISE_OI_SLIDE_PRICE']))
            col3.metric("Avg Probability", f"{recommendations_df['probability'].mean():.1f}%")
            
            # Display table
            for idx, row in recommendations_df.iterrows():
                signal_color = "🔴" if row['signal_type'] == 'RISE_OI_SLIDE_PRICE' else "🟡"
                
                with st.container():
                    st.markdown(f"### {signal_color} **{row['symbol']}** - {row['probability']:.1f}% Probability")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Price", f"INR {row['underlying_price']:.2f}")
                    col2.metric("OI Change", f"{row['oi_change']:.2f}%")
                    col3.metric("Price Change", f"{row['price_change']:.2f}%")
                    col4.metric("Signal", row['signal_type'])
                    
                    # Progress bar
                    st.progress(row['probability'] / 100)
                    st.markdown("---")
            
            # Download button
            csv = recommendations_df.to_csv(index=False)
            st.download_button(
                label="Download Recommendations as CSV",
                data=csv,
                file_name=f'short_recommendations_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv'
            )
        else:
            st.warning("No recommendations found. Please check the uploaded files.")
    else:
        st.info("👆 Upload your NSE data files above to generate recommendations")

    # Disclaimer
    st.markdown("""
    <div class="warning-box">
        <p><strong>⚠️ Disclaimer:</strong> This is for educational purposes only. Short-selling involves significant risk. Always do your own research and consult with a financial advisor before making investment decisions.</p>
    </div>
    """, unsafe_allow_html=True)

with tab2:
    st.markdown("## 📈 Model Performance & Win Ratio")
    
    # Get performance report
    report = tracker.get_performance_report()
    
    st.markdown("### Current Model Weights")
    st.dataframe(report['weights'], use_container_width=True)
    
    st.markdown("### Win Ratio (Last 30 Days)")
    win_ratios = tracker.calculate_win_ratio(days=30)
    
    if win_ratios:
        for signal_type, stats in win_ratios.items():
            st.metric(
                f"{signal_type} Win Ratio",
                f"{stats['win_ratio']:.1f}%",
                f"{stats['correct']}/{stats['total']} correct"
            )
    else:
        st.info("No predictions verified yet. Use the 'Verify Predictions' tab to check results.")

with tab3:
    st.markdown("## 🔧 Verify Predictions")
    st.info("Automatically fetch next-day prices to verify prediction accuracy and improve the model")
    
    # Get pending predictions
    today = datetime.now().strftime("%Y-%m-%d")
    pending = tracker.get_pending_predictions(today)
    
    if not pending.empty:
        st.markdown(f"### Pending Predictions for {today}")
        
        # Auto-fetch button
        if st.button("🔄 Auto-Fetch All Prices", type="primary"):
            with st.spinner("Fetching prices from Yahoo Finance..."):
                updated_count = 0
                for _, row in pending.iterrows():
                    symbol = row['symbol']
                    current_price = row['actual_price']
                    
                    # Fetch current price
                    fetched_price = tracker.fetch_stock_price(symbol)
                    
                    if fetched_price:
                        tracker.update_actual_price(today, symbol, fetched_price)
                        updated_count += 1
                        st.success(f"✅ {symbol}: INR {fetched_price:.2f}")
                    else:
                        st.warning(f"⚠️ {symbol}: Could not fetch price")
                
                st.success(f"Updated {updated_count} predictions!")
                st.rerun()
        
        st.markdown("---")
        st.markdown("### Manual Update (if auto-fetch fails)")
        
        for _, row in pending.iterrows():
            symbol = row['symbol']
            current_price = row['actual_price']
            
            with st.expander(f"Update {symbol} (Current: INR {current_price:.2f})"):
                next_day_price = st.number_input(
                    f"Next-day price for {symbol}",
                    value=float(current_price),
                    step=0.01,
                    key=f"price_{symbol}"
                )
                
                if st.button(f"Update {symbol}", key=f"update_{symbol}"):
                    tracker.update_actual_price(today, symbol, next_day_price)
                    st.success(f"✅ Updated {symbol} prediction")
                    st.rerun()
    else:
        st.info("No pending predictions to verify for today.")

# Footer
st.markdown("---")
st.markdown("""
<center>
    <p>Short-Selling Analysis System | NSE Data Analysis</p>
    <p><small>Built with Streamlit</small></p>
</center>
""", unsafe_allow_html=True)
