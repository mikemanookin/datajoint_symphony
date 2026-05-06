"""03_query_python.py — example queries from a plain Python script.

Demonstrates the patterns the team uses most:
    - native DataJoint expressions on the table classes
    - the ``db.query`` helpers for the common navigation cases
    - fetching a pandas DataFrame
    - reading raw response samples from the source HDF5 on demand
"""
from symphony_dj import connect


def main() -> int:
    with connect() as db:
        # 1. Native DataJoint — count epochs per protocol.
        counts = (db.EpochBlock).aggr(
            db.Epoch, n_epochs="count(*)"
        ).fetch(format="frame")
        print("Epochs per block (head):")
        print(counts.head())
        print()

        # 2. Filter via the query helper.
        sn_epochs = db.query.epochs_for(
            protocol_id="manookinlab.protocols.SpatialNoise"
        )
        print(f"SpatialNoise epochs: {len(sn_epochs)}")

        # 3. Hierarchy traversal.
        first_exp = db.Experiment.fetch("experiment_uuid", limit=1)
        if len(first_exp):
            uuid = first_exp[0]
            tree = db.query.tree(uuid, depth="cell")
            n_animals = len(tree.get("animals", []))
            print(f"Experiment {uuid}: {n_animals} animal(s)")

        # 4. Raw sample read (only if you have an h5_path on the experiment).
        rows = (db.Response * db.Experiment).fetch(
            "experiment_uuid", "h5_path", "epoch_uuid", "device_name", "h5path",
            limit=1, as_dict=True,
        )
        if rows and rows[0]["h5_path"]:
            from symphony_dj import h5io
            row = rows[0]
            samples = h5io.read_response_data(
                row["h5_path"],
                epoch_uuid=row["epoch_uuid"],
                device_name=row["device_name"],
                h5path_hint=row["h5path"],
            )
            print(f"Sample shape: {samples.shape}, dtype: {samples.dtype}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
