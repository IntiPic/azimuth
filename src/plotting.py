from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def save_daily_clearsky_plot(df, ghi_csk, msk_clearsky, output_dir="outputs/daily_plots"):

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = df.index[0].strftime("%Y-%m-%d")
    
    df_day = df[df["ghi"] > 0]
    ghi_csk_day = ghi_csk.loc[df_day.index]
    msk_clearsky_day = msk_clearsky.loc[df_day.index]

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.plot(df_day.index, df_day["gti"], label="GTI")
    ax.plot(df_day.index, df_day["ghi"], label="GHI")
    ax.plot(ghi_csk_day.index, ghi_csk_day, "--", label="GHI clear sky")

    ax.plot(
        df_day.index[msk_clearsky_day],
        df_day.loc[msk_clearsky_day, "ghi"],
        "r*",
        markersize=6,
        label="Clear-sky minutes"
    )

    ax.set_title(date_str)
    ax.set_ylabel("Irradiance (W/m²)")
    ax.set_xlabel("Hour")
    formatter = mdates.DateFormatter("%H:%M", tz=df_day.index.tz)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate()
    ax.legend()
    ax.grid(True)

    fig.tight_layout()

    fig.savefig(output_dir / f"{date_str}.png", dpi=200, bbox_inches="tight")

    plt.close(fig)
    
    
    
def plot_omega_fit(fit_result, date=None, output_dir="outputs/gti_fit_plots"):
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    omega = fit_result['omega']
    gti = fit_result['gti']

    a, b, c = fit_result['coef']
    omega_star = fit_result['omega_star']
    gti_star = fit_result['gti_star']

    omega_fit = np.linspace(omega.min(),omega.max(),200)
    gti_fit = np.polyval([a, b, c], omega_fit)

    fig, ax = plt.subplots(figsize=(8,5))
    ax.scatter(omega,gti,label='GTI')
    ax.plot(omega_fit,gti_fit,label='Quadratic fit')
    ax.plot(omega_star,gti_star,'ro',label=r'$\omega^\ast$')

    title = (
        f'{date}\n'
        f'a={a:.3f}, '
        f'b={b:.3f}, '
        f'c={c:.3f}\n'
        f'ω*={omega_star:.3f}°'
    )

    ax.set_title(title)

    ax.set_xlabel('Hour angle (deg)')
    ax.set_ylabel('GTI (W/m²)')

    ax.grid(True)
    ax.legend()
    
    fig.savefig(output_dir / f"{date}.png", dpi=200, bbox_inches="tight")

    return fig, ax