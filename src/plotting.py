from pathlib import Path

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