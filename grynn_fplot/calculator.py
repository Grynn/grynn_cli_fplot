"""Options calculator for manual broker data input"""

import click
from tabulate import tabulate
from grynn_fplot.core import (
    calculate_cagr_to_breakeven,
    calculate_put_annualized_return,
    calculate_implied_leverage,
    calculate_black_scholes_delta,
)


def run_calculator(spot, strike, price, dte, is_call, is_put, iv, delta):
    """Calculate option metrics from broker data"""
    
    # Validate required parameters
    if spot is None or strike is None or price is None or dte is None:
        click.echo("Error: Calculator mode requires --spot, --strike, --price, and --dte")
        click.echo("Example: fplot --calc -s 100 -k 110 -p 5.25 -d 35 --call --iv 0.35")
        return
    
    # Determine option type
    if is_call and is_put:
        click.echo("Error: Cannot specify both --call and --put")
        return
    elif not is_call and not is_put:
        click.echo("Error: Must specify either --call or --put")
        return
    
    option_type = "call" if is_call else "put"
    
    # Calculate time to expiry in years
    time_to_expiry = dte / 365.0
    
    # Calculate CAGR/Return metric
    if option_type == "call":
        return_metric = calculate_cagr_to_breakeven(spot, strike, price, dte)
        return_label = "CAGR to Breakeven"
    else:  # put
        return_metric = calculate_put_annualized_return(spot, price, dte)
        return_label = "Annualized Return"
    
    # Calculate or use provided delta
    if delta is None:
        if iv is not None:
            # Calculate delta from implied volatility
            delta = calculate_black_scholes_delta(
                spot, strike, time_to_expiry, 
                volatility=iv, option_type=option_type
            )
            delta_source = f"Calculated (IV={iv:.1%})"
        else:
            click.echo("Error: Either --iv or --delta must be provided")
            return
    else:
        delta_source = "Provided by broker"
    
    # Calculate leverage
    if delta is not None:
        leverage = abs(delta) * (spot / price)
    else:
        leverage = None
    
    # Calculate efficiency (leverage / CAGR)
    if leverage and return_metric and return_metric > 0:
        efficiency_raw = leverage / return_metric
    else:
        efficiency_raw = None
    
    # Calculate strike percentage
    strike_pct = ((strike - spot) / spot) * 100
    
    # Prepare output table
    results = [
        ["Input Parameters", ""],
        ["─" * 30, "─" * 30],
        ["Spot Price", f"${spot:.2f}"],
        ["Strike Price", f"${strike:.2f}"],
        ["Option Price", f"${price:.2f}"],
        ["Days to Expiry", f"{dte} days"],
        ["Option Type", option_type.upper()],
        ["", ""],
        ["Calculated Metrics", ""],
        ["─" * 30, "─" * 30],
        ["Strike vs Spot", f"{strike_pct:+.2f}%"],
        [return_label, f"{return_metric:.2%}"],
        ["Delta", f"{delta:+.4f} ({delta_source})"],
        ["Leverage (Ω)", f"{leverage:.2f}x" if leverage else "N/A"],
        ["Efficiency (Lev/CAGR)", f"{efficiency_raw:.2f}" if efficiency_raw else "N/A"],
    ]
    
    # Add implied volatility if calculated
    if iv is not None:
        results.insert(-4, ["Implied Volatility", f"{iv:.2%}"])
    
    click.echo()
    click.echo(tabulate(results, tablefmt="simple"))
    click.echo()
    
    # Interpretation
    click.echo("Interpretation:")
    click.echo(f"  • A 1% move in stock → ~{leverage:.1f}% move in option" if leverage else "  • Leverage unavailable")
    if efficiency_raw:
        if efficiency_raw > 100:
            click.echo(f"  • Efficiency {efficiency_raw:.0f} = Excellent (high leverage, low required movement)")
        elif efficiency_raw > 50:
            click.echo(f"  • Efficiency {efficiency_raw:.0f} = Good")
        elif efficiency_raw > 20:
            click.echo(f"  • Efficiency {efficiency_raw:.0f} = Average")
        else:
            click.echo(f"  • Efficiency {efficiency_raw:.0f} = Below average")
    click.echo()
